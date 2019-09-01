import obspython as obs
import urllib.request
import urllib.error
import json
import threading
from google.cloud import texttospeech
from google.api_core.exceptions import ResourceExhausted
import random
from WikiStuff import *
import pygame
import time
import mmap
import queue
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM

obs_manager = None
current_state = "stopped"
ui_thread = None
downloader_thread = None
text_source_name = None


# ------------------------------------------------------------


class OBSSceneManager:
	def __init__(self, text_source, image_source):
		self.image_source = image_source
		self.text_source = text_source

	def update_image(self, filename):
		image_settings = obs.obs_data_create()
		obs.obs_data_set_string(image_settings, "file", filename)
		obs.obs_source_update(self.image_source, image_settings)
		obs.obs_data_release(image_settings)

	def clear_image(self):
		self.update_image('')

	def valid(self):
		return self.text_source is not None and self.image_source is not None

	def __del__(self):
		obs.obs_source_release(self.image_source)
		obs.obs_source_release(self.text_source)

	def update_title(self, title):
		settings = obs.obs_data_create()
		obs.obs_data_set_string(settings, "text", title)
		obs.obs_source_update(self.text_source, settings)
		obs.obs_data_release(settings)


def wiki_query(url):
	try:
		with urllib.request.urlopen(url) as response:
			data = response.read()
			decoded_data = data.decode('utf-8')
			return WikiQuery(json.loads(decoded_data))

	except urllib.error.URLError as err:
		obs.script_log(obs.LOG_WARNING, "Error opening URL '" + url + "': " + err.reason)
		obs.remove_current_callback()


def ui_logic(articles_queue: queue.Queue):
	global obs_manager
	global current_state

	while current_state == 'reading':
		obs.script_log(obs.LOG_DEBUG, repr(current_state))
		wiki_article = articles_queue.get()

		article_images = wiki_article.get_filtered_images()
		obs.script_log(obs.LOG_DEBUG, wiki_article.get_title())
		obs.script_log(obs.LOG_DEBUG, repr(articles_queue.qsize()))
		obs_manager.update_title(wiki_article.get_title())
		(sound_length_seconds, file_handle) = google_tts(wiki_article.get_extract())

		current_image = 0
		while current_image == 0 or current_image < len(article_images):
			image_url = "https://en.wikipedia.org/w/api.php?action=query&titles=" + urllib.parse.quote(
				article_images[current_image]) + "&prop=imageinfo&iiprop=url&format=json"
			image_wikipedia_url = wiki_query(image_url).get_image().get_url()
			filename = sink_image(image_wikipedia_url)

			if filename is not None:
				if filename.endswith('.svg'):
					obs.script_log(obs.LOG_DEBUG, 'svg!')
					drawing = svg2rlg(filename)
					renderPM.drawToFile(drawing, "/filename.png", fmt="PNG")
					filename = '/filename.png'
				obs_manager.update_image(filename)
			current_image += 1
			time.sleep(sound_length_seconds / len(article_images))
		while pygame.mixer.music.get_busy():
			time.sleep(0.5)
		if file_handle is not None:
			file_handle.close()
		obs_manager.clear_image()


def sink_image(image_url):
	try:
		(filename, _h) = urllib.request.urlretrieve(image_url, '/filename.' + image_url[-3:])
		return filename
	except urllib.error.ContentTooShortError as err:
		obs.script_log(obs.LOG_DEBUG, repr(err))
	return None


def downloader_logic(articles_queue: queue.Queue):
	global current_state

	while current_state == 'reading':
		if articles_queue.qsize() > 5:
			time.sleep(5)
			continue
		url = "https://en.wikipedia.org/w/api.php?format=json&action=query&generator=random&grnnamespace=0&prop=images|extracts&exintro&explaintext&grnlimit=1"
		wiki_api_query = wiki_query(url)
		wiki_article = wiki_api_query.get_article()

		article_images = wiki_article.get_filtered_images()

		if article_images and len(wiki_article.get_extract()) < 5000:
			articles_queue.put(wiki_article)


def run_thread_downloader(articles_queue):
	global downloader_thread
	downloader_thread = threading.Thread(target=downloader_logic, args=(articles_queue,), daemon=True)
	downloader_thread.start()


def run_thread_ui(articles_queue):
	global ui_thread
	ui_thread = threading.Thread(target=ui_logic, args=(articles_queue,), daemon=True)
	ui_thread.start()


def google_tts(text):
	available_voices = [
		'en-AU-Wavenet-A',
		'en-AU-Wavenet-B',
		'en-AU-Wavenet-C',
		'en-AU-Wavenet-D',
		'en-GB-Wavenet-A',
		'en-GB-Wavenet-B',
		'en-GB-Wavenet-C',
		'en-GB-Wavenet-D',
		'en-US-Wavenet-A',
		'en-US-Wavenet-B',
		'en-US-Wavenet-C',
		'en-US-Wavenet-D',
		'en-US-Wavenet-E',
		'en-US-Wavenet-F',
	]
	# Instantiates a client
	client = texttospeech.TextToSpeechClient()

	# Set the text input to be synthesized
	synthesis_input = texttospeech.types.SynthesisInput(text=text if len(text) < 5000 else '')

	# Build the voice request, select the language code ("en-US") and the ssml
	# voice gender ("neutral")
	random_voice = random.choice(available_voices)
	voice = texttospeech.types.VoiceSelectionParams(language_code=random_voice[:5], name=random_voice)

	# Select the type of audio file you want returned
	pitch = random.randint(-6, 2)
	speaking_rate = round(random.uniform(0.8, 1), 2)
	audio_config = texttospeech.types.AudioConfig(
		audio_encoding=texttospeech.enums.AudioEncoding.LINEAR16,
		speaking_rate=speaking_rate,
		pitch=pitch)

	obs.script_log(obs.LOG_DEBUG, repr({'voice': random_voice, 'pitch': pitch, 'speaking_rate': speaking_rate}))

	# Perform the text-to-speech request on the text input with the selected
	# voice parameters and audio file type
	sound_length_seconds = 0
	file_handle = None
	try:
		response = client.synthesize_speech(synthesis_input, voice, audio_config)

		stop_reading()

		# The response's audio_content is binary.
		with open('hello.wav', 'wb') as out:
			# Write the response to the output file.
			out.write(response.audio_content)
		if not pygame.mixer.get_init():
			pygame.mixer.init()
		with open('hello.wav') as f:
			m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
		pygame.mixer.music.load(m)
		sound_length_seconds = pygame.mixer.Sound('hello.wav').get_length()
		pygame.mixer.music.play()
		file_handle = m

	except ResourceExhausted as err:
		obs.script_log(obs.LOG_DEBUG, repr(err))

	return sound_length_seconds, file_handle


def stop_reading():
	if pygame.mixer.get_init():
		pygame.mixer.music.stop()


def start_pressed(props, prop):
	global current_state
	refresh_manager()
	obs.script_log(obs.LOG_DEBUG, repr(current_state))
	if current_state != 'reading':
		current_state = 'reading'
		articles_queue = queue.Queue()
		run_thread_downloader(articles_queue)
		run_thread_ui(articles_queue)


def stop_pressed(props, prop):
	global current_state
	obs.script_log(obs.LOG_DEBUG, repr(current_state))
	if current_state != 'stopped':
		stop_reading()
		current_state = 'stopped'


def script_description():
	return "Reads some stuff from Wikipedia.\n\nBy Raphinait"


def script_update(settings):
	global obs_manager, text_source_name

	text_source_name = obs.obs_data_get_string(settings, "source")
	refresh_manager()


def refresh_manager():
	global obs_manager, text_source_name
	text_source = obs.obs_get_source_by_name(text_source_name)
	image_source = obs.obs_get_source_by_name("Image")
	obs_manager = OBSSceneManager(text_source, image_source)


def script_properties():
	props = obs.obs_properties_create()

	source_property = obs.obs_properties_add_list(props, "source", "Text Source", obs.OBS_COMBO_TYPE_EDITABLE,
									obs.OBS_COMBO_FORMAT_STRING)
	sources = obs.obs_enum_sources()
	if sources is not None:
		for source in sources:
			source_id = obs.obs_source_get_id(source)
			if source_id == "text_gdiplus" or source_id == "text_ft2_source":
				name = obs.obs_source_get_name(source)
				obs.obs_property_list_add_string(source_property, name, name)

		obs.source_list_release(sources)

	obs.obs_properties_add_button(props, "start", "Start", start_pressed)
	obs.obs_properties_add_button(props, "stop", "Stop", stop_pressed)
	return props
