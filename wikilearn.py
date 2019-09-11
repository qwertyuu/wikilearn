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
import ImageDownloader
from PIL import Image
import shutil
import os

obs_manager = None
current_state = "stopped"
ui_thread = None
downloader_thread = None
cleaner_thread = None
text_source_name = None
wiki_locale = "en"
downloading_path = os.path.join(os.getcwd(), 'wikilearn', 'downloading')
queued_path = os.path.join(os.getcwd(), 'wikilearn', 'queued')


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


class Audio:
	def __init__(self, file, duration):
		self.file = file
		self.duration = duration


def wiki_query(url):
	try:
		with urllib.request.urlopen(url) as response:
			data = response.read()
			decoded_data = data.decode('utf-8')
			return WikiQuery(json.loads(decoded_data))

	except Exception as err:
		obs.script_log(obs.LOG_WARNING, "Error opening URL '" + url + "': " + repr(err))
		obs.remove_current_callback()


def wikibase_query(url):
	try:
		with urllib.request.urlopen(url) as response:
			data = response.read()
			decoded_data = data.decode('utf-8')
			return WikiBaseQuery(json.loads(decoded_data))

	except Exception as err:
		obs.script_log(obs.LOG_WARNING, "Error opening URL '" + url + "': " + repr(err))
		obs.remove_current_callback()


def wikimedia_query(url):
	try:
		with urllib.request.urlopen(url) as response:
			data = response.read()
			decoded_data = data.decode('utf-8')
			return WikiMediaQuery(json.loads(decoded_data))

	except Exception as err:
		obs.script_log(obs.LOG_WARNING, "Error opening URL '" + url + "': " + repr(err))
		obs.remove_current_callback()


def image_too_small(filename):
	try:
		im = Image.open(filename)
	except Image.DecompressionBombError:
		return True
	width, height = im.size
	return width < 100 or height < 100


def ui_logic(articles_queue: queue.Queue):
	global obs_manager
	global current_state
	global queued_path

	while current_state == 'reading':
		obs.script_log(obs.LOG_DEBUG, repr(current_state))
		wiki_super_container: WikiSuperContainer = articles_queue.get()
		wiki_article = wiki_super_container.wiki_article

		obs.script_log(obs.LOG_DEBUG, wiki_article.get_title())
		obs.script_log(obs.LOG_DEBUG, repr(articles_queue.qsize()))
		obs.script_log(obs.LOG_DEBUG, repr(wiki_super_container.audio.file))
		obs_manager.update_title(wiki_article.get_title())

		with open(wiki_super_container.audio.file) as f:
			m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
		sound_length_seconds = pygame.mixer.Sound(wiki_super_container.audio.file).get_length()
		pygame.mixer.music.load(m)
		pygame.mixer.music.play()
		article_images = wiki_super_container.downloaded_images
		for article_image in article_images:
			if not pygame.mixer.music.get_busy():
				break
			obs_manager.update_image(article_image)
			time.sleep(sound_length_seconds / len(article_images))
		while pygame.mixer.music.get_busy():
			time.sleep(0.5)
		m.close()
		final_folder = os.path.join(queued_path, str(wiki_article.get_page_id()))
		shutil.rmtree(final_folder)
		obs_manager.clear_image()


def downloader_logic(articles_queue: queue.Queue):
	global current_state
	global downloading_path, queued_path, wiki_locale

	while current_state == 'reading':
		if articles_queue.qsize() > 5:
			time.sleep(5)
			continue

		url = "https://" + wiki_locale + ".wikipedia.org/w/api.php?format=json&action=query&generator=random&grnnamespace=0&prop=images|pageprops|extracts&exintro&explaintext&grnlimit=1"
		wiki_api_query = wiki_query(url)

		if wiki_api_query is None:
			continue

		wiki_article = wiki_api_query.get_article()
		wikibase_id = wiki_article.get_wikibase_id()

		if wikibase_id is None:
			continue

		wikibase_url = "https://www.wikidata.org/w/api.php?action=wbgetentities&ids=" + wikibase_id + "&props=sitelinks&formatversion=2&format=json"
		wikibase_api_query = wikibase_query(wikibase_url)

		if wikibase_api_query is None:
			continue

		wikibase_entity = wikibase_api_query.get_entity()

		if wikibase_entity is None:
			continue

		wikimedia_category = wikibase_entity.get_commons_category()
		wikimedia_api_query = None

		if wikimedia_category is not None:
			wikimedia_url = "https://commons.wikimedia.org/w/api.php?action=query&list=categorymembers&cmtitle=" + urllib.parse.quote(
				wikimedia_category) + "&cmlimit=10&cmtype=file&format=json"
			wikimedia_api_query = wikimedia_query(wikimedia_url)

		article_images = wiki_article.get_filtered_images()

		if article_images and len(wiki_article.get_extract()) < 5000:
			downloading_folder = os.path.join(downloading_path, str(wiki_article.get_page_id()))
			final_folder = os.path.join(queued_path, str(wiki_article.get_page_id()))
			os.makedirs(downloading_folder)

			tts_filename = os.path.join(downloading_folder, 'hello.wav')

			sound_length_seconds = google_tts(wiki_article.get_extract(), tts_filename)
			if sound_length_seconds is None:
				continue

			all_images = wiki_article.get_filtered_images() + (
				wikimedia_api_query.get_filenames() if wikimedia_api_query is not None else [])

			downloaded_images = []
			for article_image in all_images:
				image_url = "https://" + wiki_locale + ".wikipedia.org/w/api.php?action=query&titles=" + urllib.parse.quote(
					article_image) + "&prop=imageinfo&iiprop=url&format=json"
				image_wikipedia = wiki_query(image_url)
				if image_wikipedia is None:
					continue

				image_wikipedia = image_wikipedia.get_image()
				filename = ImageDownloader.download_image(image_wikipedia, downloading_folder)
				if filename is None:
					continue

				obs.script_log(obs.LOG_DEBUG, filename)
				downloaded_images.append(filename)

			shutil.move(downloading_folder, final_folder)
			moved_images = [os.path.join(final_folder, os.path.basename(f)) for f in downloaded_images]
			final_tts_filename = os.path.join(final_folder, 'hello.wav')

			filtered_images = [i for i in moved_images if not image_too_small(i)]

			articles_queue.put(
				WikiSuperContainer(wiki_article, filtered_images, Audio(final_tts_filename, sound_length_seconds)))


def run_thread_downloader(articles_queue):
	global downloader_thread
	downloader_thread = threading.Thread(target=downloader_logic, args=(articles_queue,), name='downloader',
										 daemon=True)
	downloader_thread.start()


def run_thread_ui(articles_queue):
	global ui_thread
	ui_thread = threading.Thread(target=ui_logic, args=(articles_queue,), name='ui', daemon=True)
	ui_thread.start()


def google_tts(text, save_to):
	global wiki_locale
	available_voices = {
		'en': [
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
		],
		'fr': [
			'fr-CA-Wavenet-A',
			'fr-CA-Wavenet-B',
			'fr-CA-Wavenet-C',
			'fr-CA-Wavenet-D',
			'fr-FR-Wavenet-A',
			'fr-FR-Wavenet-B',
			'fr-FR-Wavenet-C',
			'fr-FR-Wavenet-D',
		]
	}
	# Instantiates a client
	client = texttospeech.TextToSpeechClient()

	# Set the text input to be synthesized
	synthesis_input = texttospeech.types.SynthesisInput(text=text if len(text) < 5000 else '')

	# Build the voice request, select the language code ("en-US") and the ssml
	# voice gender ("neutral")
	random_voice = random.choice(available_voices[wiki_locale])
	voice = texttospeech.types.VoiceSelectionParams(language_code=random_voice[:5], name=random_voice)

	# Select the type of audio file you want returned
	pitch = random.randint(-3, 3)
	speaking_rate = round(random.uniform(0.9, 1.15), 2)
	audio_config = texttospeech.types.AudioConfig(
		audio_encoding=texttospeech.enums.AudioEncoding.LINEAR16,
		speaking_rate=speaking_rate,
		pitch=pitch)

	obs.script_log(obs.LOG_DEBUG, repr({'voice': random_voice, 'pitch': pitch, 'speaking_rate': speaking_rate}))

	# Perform the text-to-speech request on the text input with the selected
	# voice parameters and audio file type
	sound_length_seconds = 0
	try:
		response = client.synthesize_speech(synthesis_input, voice, audio_config)

		# The response's audio_content is binary.
		with open(save_to, 'wb') as out:
			# Write the response to the output file.
			out.write(response.audio_content)

	except ResourceExhausted as err:
		obs.script_log(obs.LOG_DEBUG, repr(err))
		return None

	return sound_length_seconds


def stop_reading():
	if pygame.mixer.get_init():
		pygame.mixer.music.stop()


def clean_files():
	global downloading_path, queued_path
	shutil.rmtree(queued_path)
	shutil.rmtree(downloading_path)
	os.makedirs(queued_path)
	os.makedirs(downloading_path)


def start_pressed(props, prop):
	global current_state
	refresh_manager()
	obs.script_log(obs.LOG_DEBUG, repr(current_state))
	if current_state != 'reading':
		current_state = 'reading'
		clean_files()
		if not pygame.get_init():
			pygame.init()
		if not pygame.mixer.get_init():
			pygame.mixer.init()
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
	global obs_manager, text_source_name, wiki_locale

	text_source_name = obs.obs_data_get_string(settings, "source")
	wiki_locale = obs.obs_data_get_string(settings, "locale")
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
	obs.obs_properties_add_text(props, "locale", "Wiki locale", obs.OBS_TEXT_DEFAULT)
	return props
