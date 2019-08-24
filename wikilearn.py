import obspython as obs
import urllib.request
import urllib.error
import json
from playsound import playsound
import threading
from google.cloud import texttospeech

interval = 30
source_name = ""


# ------------------------------------------------------------

def update_text():
	global interval
	global source_name
	url = "https://en.wikipedia.org/w/api.php?format=json&action=query&generator=random&grnnamespace=0&prop=images|extracts&exintro&explaintext&grnlimit=1"

	source = obs.obs_get_source_by_name(source_name)
	image = obs.obs_get_source_by_name('Image')
	if source is not None:
		try:
			with urllib.request.urlopen(url) as response:
				data = response.read()
				text = data.decode('utf-8')

				wiki_object = json.loads(text)
				page = list(wiki_object['query']['pages'].values())[0]
				if 'images' in page:
					article_images = [i['title'] for i in page['images'] if i['title'][-3:] in ['jpg', 'png']]

					if len(article_images) > 0:
						obs.script_log(obs.LOG_DEBUG, repr(page['extract']))
						image_url = "https://en.wikipedia.org/w/api.php?action=query&titles=" + urllib.parse.quote(article_images[0]) + "&prop=imageinfo&iiprop=url&format=json"

						try:
							with urllib.request.urlopen(image_url) as image_response:
								image_data = image_response.read()
								image_text = image_data.decode('utf-8')
								wiki_image_object = json.loads(image_text)
								image_wikipedia_url = list(wiki_image_object['query']['pages'].values())[0]['imageinfo'][0]['url']
								(filename, _h) = urllib.request.urlretrieve(image_wikipedia_url, '/filename.' + image_wikipedia_url[-3:])

								image_settings = obs.obs_data_create()
								obs.obs_data_set_string(image_settings, "file", filename)
								obs.obs_source_update(image, image_settings)
								obs.obs_data_release(image_settings)

						except urllib.error.URLError as err:
							obs.script_log(obs.LOG_WARNING, "Error opening URL '" + image_url + "': " + err.reason)
							obs.remove_current_callback()
					else:
						image_settings = obs.obs_data_create()
						obs.obs_data_set_string(image_settings, "file", '')
						obs.obs_source_update(image, image_settings)
						obs.obs_data_release(image_settings)
				else:
					image_settings = obs.obs_data_create()
					obs.obs_data_set_string(image_settings, "file", '')
					obs.obs_source_update(image, image_settings)
					obs.obs_data_release(image_settings)

				settings = obs.obs_data_create()
				obs.obs_data_set_string(settings, "text", page['title'])
				obs.obs_source_update(source, settings)
				obs.obs_data_release(settings)
				run_thread_tts(page['extract'], finished)

		except urllib.error.URLError as err:
			obs.script_log(obs.LOG_WARNING, "Error opening URL '" + url + "': " + err.reason)
			obs.remove_current_callback()

		obs.obs_source_release(source)


def finished():
	update_text()


def run_thread_tts(text, finished_callback):
	threading.Thread(target=play_sound, args=(text, finished_callback), daemon=True).start()


def play_sound(text, finished_callback):
	# Instantiates a client
	client = texttospeech.TextToSpeechClient()

	# Set the text input to be synthesized
	synthesis_input = texttospeech.types.SynthesisInput(text=text)

	# Build the voice request, select the language code ("en-US") and the ssml
	# voice gender ("neutral")
	voice = texttospeech.types.VoiceSelectionParams(
		language_code='en-GB',
		name='en-GB-Wavenet-A',
		ssml_gender=texttospeech.enums.SsmlVoiceGender.FEMALE)

	# Select the type of audio file you want returned
	audio_config = texttospeech.types.AudioConfig(
		audio_encoding=texttospeech.enums.AudioEncoding.MP3,
		speaking_rate=0.8,
		pitch=-3)

	# Perform the text-to-speech request on the text input with the selected
	# voice parameters and audio file type
	response = client.synthesize_speech(synthesis_input, voice, audio_config)

	# The response's audio_content is binary.
	with open('hello.mp3', 'wb') as out:
		# Write the response to the output file.
		out.write(response.audio_content)
	playsound('hello.mp3')
	finished_callback()


def refresh_pressed(props, prop):
	update_text()


# ------------------------------------------------------------

def script_description():
	return "Updates a text source to the text retrieved from a URL at every specified interval.\n\nBy Raphinait"


def script_update(settings):
	global source_name

	source_name = obs.obs_data_get_string(settings, "source")

def script_properties():
	props = obs.obs_properties_create()

	p = obs.obs_properties_add_list(props, "source", "Text Source", obs.OBS_COMBO_TYPE_EDITABLE,
									obs.OBS_COMBO_FORMAT_STRING)
	sources = obs.obs_enum_sources()
	if sources is not None:
		for source in sources:
			source_id = obs.obs_source_get_id(source)
			if source_id == "text_gdiplus" or source_id == "text_ft2_source":
				name = obs.obs_source_get_name(source)
				obs.obs_property_list_add_string(p, name, name)

		obs.source_list_release(sources)

	obs.obs_properties_add_button(props, "button", "Refresh", refresh_pressed)
	return props
