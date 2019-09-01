import urllib.request

current_position = 0
max_position = 10


def download_image(image_wikipedia_url):
	global current_position
	current_position = current_position + 1
	if current_position > max_position:
		current_position = 1
	(filename, _h) = urllib.request.urlretrieve(image_wikipedia_url, '/filename' + str(current_position) + '.' + image_wikipedia_url[-3:])
	return filename
