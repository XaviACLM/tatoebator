from typing import Optional, Callable, Any


class AnkiTemplateRendererContentManager:
    # data isn't used here. check where it's used outside, see if relevant (see what to put in it at all)
    def __init__(self, media_provider, data):
        self._media_provider = media_provider
        self._data = data
        self._on_unload_callbacks = []

    def load_media(self, path, dictionary, on_load, on_unload: Optional[Callable[..., Any]]):
        image_url = self._media_provider.get_media()
        if image_url is None: return
        on_load(image_url)
        if on_unload is not None:
            self._on_unload_callbacks.append(on_unload)

    def unload_all(self):
        # todo when ever will we use this??
        for unload_callback in self._on_unload_callbacks:
            unload_callback(True)
        self._on_unload_callbacks = []

    def prepare_link(self, element, href, internal):
        # this is how yomitan itself handles it - internal links are left in there, but they go nowhere
        element['href'] = '#' if internal else href