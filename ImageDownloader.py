import requests
import WikiStuff
import os
import time
import urllib.error
from pathvalidate import sanitize_filename


def download_image(image_wikipedia: WikiStuff.WikiImage, folder):
	try:
		wikipedia_filename = image_wikipedia.get_title()
		filename = os.path.join(folder, sanitize_filename(wikipedia_filename))
		headers = {'User-Agent': 'WikiLearnBot/1.0 (https://raphaelcote.com/en; cotlarrc@gmail.com) obs/1.0'}

		response = requests.get(image_wikipedia.get_url(), headers=headers)
		with open(filename, "wb") as f:
			f.write(response.content)
		time.sleep(0.5)
	except Exception as err:
		print(err)
		return None
	return filename
