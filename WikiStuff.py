class WikiSuperContainer:
	def __init__(self, wiki_article, downloaded_images, audio):
		self.wiki_article = wiki_article
		self.downloaded_images = downloaded_images
		self.audio = audio


class WikiArticle:
	wiki_article_object = {}

	def __init__(self, wiki_object):
		self.wiki_object = wiki_object

	def get_filtered_images(self, extension_filter=None):
		if extension_filter is None:
			extension_filter = ['jpg', 'png']

		return [i['title'] for i in self.wiki_object.get('images', []) if i['title'][-3:] in extension_filter]

	def get_wikibase_id(self):
		return self.wiki_object.get('pageprops', {}).get('wikibase_item')

	def get_page_id(self):
		return self.wiki_object.get('pageid')

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
		return self.wiki_object.get('imageinfo', [{}])[0].get('url')


class WikiQuery:
	wiki_object = {}

	def __init__(self, wiki_object):
		self.wiki_object = wiki_object

	def get_articles_raw(self):
		return list(self.wiki_object['query']['pages'].values())

	def get_articles_count(self):
		return len(self.get_articles_raw())

	def get_article(self, index=0) -> WikiArticle:
		return WikiArticle(self.get_articles_raw()[index])

	def get_image(self, index=0) -> WikiImage:
		return WikiImage(self.get_articles_raw()[index])


class WikiBaseEntity:
	wiki_entity_object = {}

	def __init__(self, wiki_object):
		self.wiki_object = wiki_object

	def get_commons_category(self):
		return self.wiki_object.get('sitelinks', {}).get('commonswiki', {}).get('title')


class WikiBaseQuery:
	wiki_object = {}

	def __init__(self, wiki_object):
		self.wiki_object = wiki_object

	def get_entities_raw(self):
		return list(self.wiki_object['entities'].values())

	def get_entity(self, index=0) -> WikiBaseEntity:
		entities = self.get_entities_raw()
		return WikiBaseEntity(entities[index]) if len(entities) > 0 else None


class WikiMediaQuery:
	def __init__(self, wiki_object):
		self.wiki_object = wiki_object

	def get_filenames(self):
		extension_filter = ['jpg', 'png']
		return [r['title'] for r in self.wiki_object.get('query', {}).get('categorymembers', []) if r['title'][-3:] in extension_filter]
