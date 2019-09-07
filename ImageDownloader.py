import urllib.request
import WikiStuff
import os
from pathvalidate import sanitize_filename


def download_image(image_wikipedia: WikiStuff.WikiImage, folder):
	wikipedia_filename = image_wikipedia.get_title()
	(filename, _h) = urllib.request.urlretrieve(image_wikipedia.get_url(), os.path.join(folder, sanitize_filename(wikipedia_filename.replace('File:', ''))))
	return filename
