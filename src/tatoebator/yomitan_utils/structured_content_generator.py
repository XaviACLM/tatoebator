from typing import Dict
import re

from bs4 import BeautifulSoup

from .anki_template_renderer_content_manager import AnkiTemplateRendererContentManager


class StructuredContentGenerator:
    def __init__(self, content_manager: AnkiTemplateRendererContentManager):
        self._content_manager = content_manager

    # todo does the dictionary actually get used anywhere at all?
    #  by the content manager, sure, but doesn't it keep its own reference?
    def _create_structured_content_generic_element(self, content, dictionary):
        tag = content['tag']
        if tag == 'br':
            return self._create_structured_content_element(tag, content, dictionary, 'Simple', False, False)
        if tag in ['ruby', 'rt', 'rp']:
            return self._create_structured_content_element(tag, content, dictionary, 'Simple', True, False)
        if tag == 'table':
            return self._create_structured_content_table_element(tag, content, dictionary)
        if tag in ['th', 'td']:
            return self._create_structured_content_element(tag, content, dictionary, 'table-cell', True, True)
        if tag in ['thead', 'tbody', 'tfoot', 'tr']:
            return self._create_structured_content_element(tag, content, dictionary, 'table', True, False)
        if tag in ['div', 'span', 'ol', 'ul', 'li', 'details', 'summary']:
            return self._create_structured_content_element(tag, content, dictionary, 'simple', True, True)
        if tag == 'img':
            return self.create_definition_image(content, dictionary)
        if tag == 'a':
            return self._create_link_element(content, dictionary)
        return None

    def _set_node_attr(self, node, attr, value):
        node[attr] = value

    def _create_structured_content_element(self, tag, content, dictionary, kind, has_children, has_style):

        # todo added this - very hacky, but what was going on before?
        if kind == 'table': tag = 'table'

        node = self._create_element(tag, f'gloss-sc-{tag}')
        data = content.get('data')

        if data is not None:
            for key, value in data.items():
                node[f'data-{key}'] = value

        if kind == 'table-cell':
            cell = node
            col_span = content.get('colSpan')
            row_span = content.get('rowSpan')

            # todo ...?
            # print([col_span, row_span, content])

            if col_span is not None:
                self._set_node_attr(cell, 'colSpan', col_span)
                if not isinstance(col_span, int):
                    raise Exception("weird col_span data")
            if row_span is not None:
                self._set_node_attr(cell, 'rowSpan', row_span)
                if not isinstance(row_span, int):
                    raise Exception("weird row_span data")

        if has_style:
            style = content.get('style')
            title = content.get('title')
            open = content.get('open')
            if style is not None:
                self._set_structured_content_element_style(node, style)
            if isinstance(title, str):
                self._set_node_attr(node, 'title', title)
            if isinstance(open, bool) and open:
                # todo this one is an actual setAttribute call in the js - whatever that means
                self._set_node_attr(node, 'open', '')

        if has_children:
            self._append_structured_content(node, content.get('content'), dictionary)

        return node

    def _append_structured_content(self, container, content, dictionary):
        if isinstance(content, str):
            if len(content) > 0:
                container.append(self._create_text_node(content))
            return
        if content is None:
            return
        if hasattr(content, '__iter__') and not isinstance(content, dict):  # we already know it's not a str
            for item in content:
                self._append_structured_content(container, item, dictionary)
            return
        node = self._create_structured_content_generic_element(content, dictionary)
        if node is not None:
            container.append(node)

    def _create_text_node(self, content):
        # todo check out how browser does this to copy the html syntax
        lines = content.split("\n")
        node = self._create_element('p', None)
        line_break = BeautifulSoup('<br/>', 'html.parser').find()
        for line in lines[:-1]:
            node.append(line)
            node.append(line_break)
        node.append(lines[-1])
        return node

    def _create_element(self, tag_name, class_name):
        return BeautifulSoup(f"<{tag_name} class='{class_name}'></{tag_name}>", 'html.parser').find()

    def _create_structured_content_table_element(self, tag, content, dictionary):
        container = self._create_element('div', 'gloss-sc-table-container')
        table = self._create_structured_content_element(tag, content, dictionary, 'table', True, False)
        container.append(table)
        return container

    def _set_structured_content_element_style(self, node, content_style):
        style = self._get_node_style(node)

        attr_names = ['fontStyle',
                      'fontWeight',
                      'fontSize',
                      'color',
                      'background',
                      'backgroundColor',
                      'textDecorationStyle',
                      'textDecorationColor',
                      'borderColor',
                      'borderStyle',
                      'borderRadius',
                      'borderWidth',
                      'clipPath',
                      'verticalAlign',
                      'textAlign',
                      'textEmphasis',
                      'textShadow',
                      'margin',
                      'padding',
                      'paddingTop',
                      'paddingLeft',
                      'paddingRight',
                      'paddingBottom',
                      'wordBreak',
                      'whiteSpace',
                      'cursor',
                      'listStyleType']
        for attr_name in attr_names:
            attr_value = content_style.get(attr_name)
            if attr_value is not None:
                style[attr_name] = attr_value

        attr_names = ['marginTop',
                      'marginLeft',
                      'marginRight',
                      'marginBottom']
        for attr_name in attr_names:
            attr_value = content_style.get(attr_name)
            if isinstance(attr_value, str):
                style[attr_name] = attr_value
            elif attr_value is not None:
                style[attr_name] = f'{attr_value}em'

        text_decoration_line = content_style.get('textDecorationLine')
        if isinstance(text_decoration_line, str):
            style['textDecoration'] = text_decoration_line
        elif hasattr(text_decoration_line, '__iter__'):  # it must be Collection[str]
            style['textDecoration'] = ' '.join(text_decoration_line)

        self._set_node_style(node, style)

    def _create_link_element(self, content, dictionary):
        href = content.get('href')
        internal = href.startswith('?')

        if internal:
            assert href.startswith("?query=")
            # not worth it to try implement this outsite yomitan
            # todo or is it? some definitions, esp those in jitendex, are just a reference to another def
            #  if nothing else they should certainly be excluded
            #  but how do you detect if the content of a def is just the href?
            return None
            # href = `${location.protocol}//${location.host}/search.html${href.length > 1 ? href : ''}`;

        node = self._create_element('a', 'gloss-link')
        node['data-external'] = 'false' if internal else 'true'

        text = self._create_element('span', 'gloss-link-text')
        node.append(text)

        self._append_structured_content(text, content.get('content'), dictionary)

        if not internal:
            icon = self._create_element('span', 'gloss-external-link-icon icon')

            # todo we still need to create the actual icon
            icon.append("(icon go here)")

            self._set_node_attr(icon, 'data-icon', 'external-link')
            node.append(icon)

        self._content_manager.prepare_link(node, href, internal)

        return node

    def _get_node_style(self, node) -> Dict[str, str]:
        style = node.get('style')
        if style is None:
            style = dict()
        elif isinstance(style, str):
            # for proper formatting - again, assume js handles this automatically
            # need to set properties st html can read them - does js do this auto too? why???
            style = {key: value for key, value in map(lambda style_elem: style_elem.split(":"), style.split(";"))}
        return style

    def _set_node_style(self, node, style: Dict[str, str], ensure_no_camel=True):
        f = lambda s: re.sub(r'([A-Z])', lambda m: '-' + m.group(1).lower(), s) if ensure_no_camel \
            else lambda x: x
        style = ";".join(f'{f(key)}:{value}' for key, value in style.items())
        self._set_node_attr(node, 'style', style)

    def create_definition_image(self, data, dictionary):
        #print("image data - checking if it's snakecase or what...:")
        #print(data)
        #input()
        path = data.get("path")
        width = data.get("width") or 100
        height = data.get("height") or 100
        preferred_width = data.get("preferredWidth")
        preferred_height = data.get("preferredHeight")
        title = data.get("title")
        pixelated = data.get("pixelated")
        image_rendering = data.get("imageRendering")
        appearance = data.get("appearance")
        background = data.get("background")
        collapsed = data.get("collapsed")
        collapsible = data.get("collapsible")
        vertical_align = data.get("verticalAlign")
        border = data.get("border")
        border_radius = data.get("borderRadius")
        size_units = data.get("sizeUnits")

        has_preferred_width = preferred_width is not None
        has_preferred_height = preferred_height is not None
        inv_aspect_ratio = preferred_height / preferred_width if (
                has_preferred_height and has_preferred_width) else height / width
        used_width = preferred_width if has_preferred_width else (
            preferred_height / inv_aspect_ratio if has_preferred_height else (
                width
            )
        )

        node = self._create_element('a', 'gloss-image-link')

        self._set_node_attr(node, 'target', '_blank')
        self._set_node_attr(node, 'rel', 'noreferrer noopener')

        image_container = self._create_element('span', 'gloss-image-container')
        node.append(image_container)

        aspect_ratio_sizer = self._create_element('span', 'gloss-image-sizer')
        image_container.append(aspect_ratio_sizer)

        image_background = self._create_element('span', 'gloss-image-background')
        image_container.append(image_background)

        overlay = self._create_element('span', 'gloss-image-container-overlay')
        image_container.append(overlay)

        link_text = self._create_element('span', 'gloss-image-link-text')
        link_text['text'] = 'Image'
        node.append(link_text)

        # here yomitan would check if it has the adequate content manager, and if so
        # put a listener on node's click event to open the image in a new tab
        # i don't think we can do that? but it might be good to investigate later

        node["data-path"] = path
        node["data-dictionary"] = dictionary
        # todo again watch the snake case - here because it's dataset attrs
        #  i'm starting to wonder - do any of these dataset attrs actually matter?
        #  it feels like all of them are internal yomitan stuff
        node["data-imageLoadState"] = 'not-loaded'
        node["data-hasAspectRatio"] = 'true'
        node["data-imageRendering"] = image_rendering if isinstance(image_rendering, str) else (
            'pixelated' if pixelated else 'auto'
        )
        node["data-appearance"] = background if isinstance(background, str) else 'auto'
        node["data-background"] = str(background).lower() if isinstance(background, bool) else 'true'
        node["data-collapsed"] = str(collapsed).lower() if isinstance(collapsed, bool) else 'false'
        node["data-collapsible"] = str(collapsible).lower() if isinstance(collapsible, bool) else 'true'

        if isinstance(vertical_align, str):
            node["data-verticalAlign"] = vertical_align

        if isinstance(size_units, str) and (has_preferred_width or has_preferred_height):
            node["data-sizeUnits"] = size_units

        # this just the line
        # aspectRatioSizer.style.paddingTop = `${invAspectRatio * 100} % `;
        style = self._get_node_style(aspect_ratio_sizer)
        style['padding-top'] = f"{int(inv_aspect_ratio * 100)}%"
        self._set_node_style(aspect_ratio_sizer, style)

        style = self._get_node_style(image_container)
        if isinstance(border, str):
            style['border'] = border
        if isinstance(border_radius, str):
            style['border-radius'] = border_radius
        style['width'] = f"{used_width}em"
        self._set_node_style(image_container, style)

        image_container['title'] = title

        # in js, the rest of this function happens only if _contentManager is non-null (exc return obv)

        # here this line:
        #    const image = this._contentManager instanceof DisplayContentManager ?
        #        /** @type {HTMLCanvasElement} */ (this._createElement('canvas', 'gloss-image')) :
        #        /** @type {HTMLImageElement} */ (this._createElement('img', 'gloss-image'));
        # i seem to recall the alternative to a DisplayContentManager was something-anki-something-something
        # it will probably be better for us to go with that, then
        # (that reminds me of the internal link stuff - how do anki cards handle that??

        image = self._create_element('img', 'gloss-image')
        style = self._get_node_style(image)
        if size_units == 'em' and (has_preferred_width and has_preferred_height):
            em_size = 14

            # here is
            # const scaleFactor = 2 * window.devicePixelRatio;
            # don't think we can know that from here (perhaps later on we could make it so this takes a config
            # with all these unknown values). the usual 'fallback' value for this is 1, so
            scale_factor = 2
            style['width'] = f"{used_width}em"
            style['height'] = f"{used_width * inv_aspect_ratio}em"
            image['width'] = used_width * em_size * scale_factor
        else:
            image['width'] = used_width

        image['height'] = image['width'] * inv_aspect_ratio

        style['width'] = '100%'
        style['height'] = '100%'

        self._set_node_style(image, style)
        image_container.append(image)

        return node

    def append_structured_content(self, node, content, dictionary):
        node['class'].append('structured-content')
        self._append_structured_content(node, content, dictionary)

    def create_structured_content(self, content, dictionary):
        node = self._create_element('span', 'structured-content')
        self._append_structured_content(node, content, dictionary)
        return node
