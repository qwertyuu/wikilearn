class WikiArticle:
	wiki_article_object = {}

	def __init__(self, wiki_object):
		self.wiki_object = wiki_object

	def get_filtered_images(self, extension_filter=None):
		if extension_filter is None:
			extension_filter = ['jpg', 'png']

		return [i['title'] for i in self.wiki_object.get('images', []) if i['title'][-3:] in extension_filter]

	def get_title(self):
		return self.wiki_object.get('title')

	def get_extract(self):
		return self.wiki_object.get('extract')

	def get_base_object(self):
		return self.wiki_object


class WikiImage:
	wiki_article_object = {}

	def __init__(self, wiki_object):
		self.wiki_object = wiki_object

	def get_title(self):
		return self.wiki_object.get('title')

	def get_url(self):
		return self.wiki_object.get('imageinfo', [])[0].get('url')


class WikiQuery:
	wiki_object = {}

	def __init__(self, wiki_object):
		self.wiki_object = wiki_object

	def get_pages(self):
		return list(self.wiki_object['query']['pages'].values())

	def get_page_count(self):
		return len(self.get_pages())

	def get_article(self, index=0) -> WikiArticle:
		return WikiArticle(self.get_pages()[index])

	def get_image(self, index=0) -> WikiImage:
		return WikiImage(self.get_pages()[index])
