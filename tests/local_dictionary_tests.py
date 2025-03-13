import os
import json
import zipfile

downloads_dir = r"C:\Users\xavia\Downloads"
dicts_zip_filepath = os.path.join(downloads_dir, "Japanese-20250312T213821Z-001.zip")

with zipfile.ZipFile(dicts_zip_filepath, "r") as dicts_zip:
    for dict_zipinfo in dicts_zip.filelist:
        dict_zipfilename = dict_zipinfo.filename
        print(dict_zipfilename)
        with dicts_zip.open(dict_zipfilename,'r') as dict_zipfile:
            with zipfile.ZipFile(dict_zipfile,'r') as dict_zip:
                #print('index.json' in [x.filename for x in dict_zip.filelist])
                files = set(map(lambda x: x.split("/")[0], [x.filename for x in dict_zip.filelist]))
                print("\t",files)
                if 'index.json' not in files: continue
                with dict_zip.open('index.json','r') as f:
                    print("\t",f.read().decode('utf-8'))

# jesus christ the yomichan format is MASSIVE
# we need an action plan here.
# a lot of extraneous html data. really we'd be fine throwing most of it away
# but we need it to be user readable. its probably better to parse it. word table will change quite a bit to accomodate
# we look for one word (or several at a time)
#  we could gather metadata (frequency ratings). you know what, that's probably a good idea and not too hard.
#   let me check the dicts
#    innocentranked looks like [["要る", "freq", 1], ["から", "freq", 2], ["板", "freq", 3]
#    but aozora bunko looks a bit weird: [["見","freq",{"value":1,"displayValue":"1 (12407)"}],["思","freq",{"value":2,"displayValue":"2 (12319)"}]
#    conjecture that "freq"/"value" is just a ranking of which kanjo are more common ON EACH DICT, not necessarily related
#    display_value is well, meant for display, guessing aozora bunko displays the actual count of ocurrences
#   let's not overcomplicate: just show sth like
#   freq rankings:
#    #67 on Aozora Bunko
#    #316 on innocentranked
#   users are smart, they can figure it out
#   we get this data from term_meta_bank_i.json files in [JA Freq] dicts
#  but most importantly we look for definitions.
#   (...looked at the files for a while)
#   jesus christ. look at jitendex:
#    ["管理対象", "かんりたいしょう", "", "", 0, [{"type": "structured-content", "content": [{"tag": "div", "content":
#    [{"tag": "span", "title": "noun (common) (futsuumeishi)", "style": {"fontSize": "0.8em", "fontWeight": "bold",
#    "padding": "0.2em 0.3em", "wordBreak": "keep-all", "borderRadius": "0.3em", "verticalAlign": "text-bottom",
#    "backgroundColor": "#565656", "color": "white", "cursor": "help", "marginRight": "0.25em"}, "data": {"code": "n"},
#    "content": "noun"}, {"tag": "span", "style": {"fontSize": "0.8em", "fontWeight": "bold", "padding": "0.2em 0.3em",
#    "wordBreak": "keep-all", "borderRadius": "0.3em", "verticalAlign": "text-bottom", "backgroundColor": "purple",
#    "color": "white", "marginRight": "0.25em"}, "data": {"code": "comp"}, "content": "computing"}, {"tag": "div",
#    "content": {"tag": "ul", "style": {"listStyleType": "none", "paddingLeft": "0"}, "data": {"content": "glossary"},
#    "content": {"tag": "li", "content": "managed object"}}}]}, {"tag": "div", "style": {"fontSize": "0.7em",
#    "textAlign": "right"}, "data": {"content": "attribution"}, "content": {"tag": "a", "href":
#    "https://www.edrdg.org/jmwsgi/entr.py?svc=jmdict&q=2347770", "content": "JMdict"}}]}], 2347770, ""]
#   the actual definition there is 'managed object', w the extra bit of 'computing', which i assume is language domain
#   this is rather troubling. as far as i can't tell there isn't any canonical distinction in the json between the
#   actual definition and the tag.
#   which makes enough sense. yt's job is just to show you the dictionary, you do the thinking
#   this in fact makes sense for us too (hence the fact that yt already has anki integration), but it means that we
#   need to be able to parse this whole mess into html
#   which despite my repeated googling doesn't seem like something that's readily available on github? what the hell is
#   up with that???
#   i guess we just have to
#   figuring out how to display html in the boxes - you know, the boxes - shouldn't be too hard
#   it'll need a redesign to make any sense.
#   and the html parser can't be too complicated. it does concern me whether the yt structured-content format can
#   actually be cleanly mapped onto html, but by god i'm just going to ignore anything that's too complicated to fit
#   images will need a bit of extra processing.
#   . . .
#   or we could do some preliminary inspection - look through the dicts and count how many words each of them has
#   if it turns out that 98% of the words are in like three dictionaries we might aswell just look at the specific formats
#   like if we scrape jisho but jisho is in fact just jmedict/jitendex then surely jitendex's format is, despite all
#   the fucking around, regular in itself, so we should be able to write a nice JitendexInterface (best pick a better name)
#   that looks through the mess and kicks out a standarized Definition object (for either lang) - with the text of the
#   definition itself, possibly support for furigana, definitely support for images, maybe some tags or whatever -
#   depending on which dict we look at.
#   but really, if we have pictures we'll end up having to redesign the word table either way. god
#   ...
#   some of the other dicts are thankfully pretty simple - more of that fifth element just being a ['<definition>']
#   ...
#   sometimes if you keep looking down through the 'content' elements it turns out you arrive at a single string.
#   we can take those and ignore the html probably
#   dude, no. wait a minute. look at the antonym dict.
#   ["楽","らく","","",0,
#     [{"type": "structured-content","content": [{
#             "tag": "div","data": {"name": "解説部"},"content": [{
#                 "tag": "div","data": {"name": "大語義"},"content": {
#                   "tag": "div","data": {"name": "語義"},"content": [{
#                       "tag": "span","data": {"name": "対義語"},
#                       "content": "苦   (く)"}]}}]}]}],0,""]
#   the "definition" is just 苦, which is an ANTONYM. the fact that it is an antonym is contained in the 'name' of the
#   span that contains the definition. the 'name' isn't even something that shows up - i'm supposed to know how to
#   interpret this myself? even if i am, does that mean I also have to care about the 解説部, 大語義, 語義 tags?
#   or if i want to parse this naively am i supposed to tell the user each time that he's about to read a meaning,
#   subsection of general meaning in the explanation section? what the hell, man?
#   checked that 対義語 does not appear on the relevant schema. Seriously what the hell?
#   and the dictionary does not appear to carry any css information or anything about how to handle it??????????????
#   god! man! what do i do with this shit?
#   all the [JA-JA something] might just be too spicy for me. best stick to [JA-JA]
#   . . .
#   okay, really, action plan: the first step is to programmatically investigate the dicts. for each count
#   how many words within
#   how many of these have a definition (or several) which is thankfully just a single string
#   we might get favorable results from this
#   . . .
#   moreover be absolutely sure to include the images where possible
#   . . .
#   the donna toki doo tsukau nihongo something something makes good on its name: the definition is mostly just a bunch of examples
#   oh yeah on that subject i forgot to say we should look through the [JA Grammar]-s too. I love the ones with the pictures
#   a lot of the grammars blur the line between languages, though.
#   . . .
#   having slept on it (haven't done anything yet) i can't help but think it's really weird that yomitan doesn't expose an api for this
#   there are some issues on gh about it. one with updates two weeks ago, in fact
#   but i guess it's a bit too much to ask? what i'm asking for specifically, i mean, i don't know what those apis plan to expose
#   but the fact of the matter is that all the info is there and turning it into html shouldn't be that hard, and more to the point,
#   it's not particularly meaningful to want to do this in yomichan as opposed to python b/c it's not like the communication between them
#   can be all that clean, either
#   ...maybe. that's a bit of a flimsy argument. but it is true that it's a slightly odd request to want access to the _rendering_ portion of yomichan
#   well, yomitan, whatever. speaking of, one thing we _should_ integrate is to look for dicts in yomitan's files
#   speaking of, where are my yomitan's files?