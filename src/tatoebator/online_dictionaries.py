import requests
from bs4 import BeautifulSoup, NavigableString



requests_session = requests.Session()
requests_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
})



def get_meaning_from_tanoshii(word: str) -> str:
    url = f"https://www.tanoshiijapanese.com/dictionary/index.cfm?j={word}&e=&search=Search+>"
    response = requests_session.get(url)

    if response.status_code != 200:
        raise Exception(f"Something went wrong with the tanoshiijp request - status code {response.status_code}")

    soup = BeautifulSoup(response.content, 'html.parser')
    content_elem = soup.find('div',id='cncontentbody')
    decider_elem = content_elem.contents[1]
    if decider_elem.name=='form':
        for elem in decider_elem.find_all('div', class_='vocabulary'):
            word_elem = elem.find('span', class_='copyable')
            found_word = "".join([elem.text for elem in word_elem.find_all('rb')])
            if not found_word: found_word = word_elem.text
            if word != found_word: continue
            break #grab the first match (immediate nonetype exception otherwise)

        text = "\n".join([ol_elem.text[1:-1] for ol_elem in elem.find_all('ol')])
        text = "- "+text.replace("\n","\n- ")
        if "\n" not in text: text = text[2:]
        
        return text

    elif decider_elem.name=='div':
        #jp_elem = decider_elem.find('span', class_='copyable')
        #jp_text = "".join([elem.text for elem in jp_elem.find_all('rb')])
        text = "\n".join([ol_elem.text[1:-1] for ol_elem in decider_elem.find_all('ol')])
        text = "- "+text.replace("\n","\n- ")
        if "\n" not in text: text = text[2:]
        
        return text
    else:
        raise Exception("Tanoshiijp webpage had unexpected format")

def get_definition_from_weblio(word: str) -> str:
    url = f"https://ejje.weblio.jp/english-thesaurus/content/{word}"
    response = requests_session.get(url)

    if response.status_code != 200:
        raise Exception(f"Something went wrong with the tanoshiijp request - status code {response.status_code}")

    soup = BeautifulSoup(response.content, 'html.parser')
    table_elem = soup.find('tbody')
    #29??
    text = "\n- ".join([elem.text[29:] for elem in table_elem.find_all('p', class_='wdntTCLJ')])
    if "\n" in text: text = "- "+text
    return text

#maybe eventually? https://eow.alc.co.jp/search?q=%e3%81%99%e3%82%8b -> translations, usage, but ehh

#TODO implement a couple other sources for translations and definitions (jisho, tangorin)
#TODO deal with kanshudo rate limiting if possible (see requests?)
#TODO - tanoshii japanese multiple block search may also match based on alternate written forms

#TODO some stuff like suru, aru, ra, tachi might be best to specifically exclude - best left to a grammar deck
#if nothing else, dake seems less complex than suru but it's a grammar word anyway
#TODO think about what to do w words that seem to have nothing going on - 遣る瀬
#might be related to the splitting mode? but there was also that kare-ra thing... investigate a bit
#likewise 箍 (hoop, like from a barrel) gets split out of 箍外する (to break free from restraints). needs fine-tuning...
#yarusenai too gets split as yaruse-nai which i guess makes sense but it doesn't appear that way on jisho/tjp/tangorin
#sol: just don't include words if they have <5 example sentences - add separate menu for adding words yourself, giving your own example sentences
#sudachi may process these wrong - be sure to hardcode the lexical words in the database (and later on use only those and not sudachi)

#TODO progress indicators for generation of everything on the table
#TODO "generate everything" button
#TODO ability to select/unselect words within table

#TODO hide cmd's (sudachi?) and voicevoxes

#TODO create notetype, deck
#TODO note creation
#TODO annotate on database whether sentences are fully known or fully in database
#TODO write function that updates the above, obviously, and eventually add logic to run it periodically
#TODO card html - esp care w the logic on the sentences - separate known, discard remainder if have enough, etc
#and the random sorting, minute-based

#TODO fix doj furigana
#TODO port decks (incl. rtk to migaku... somehow?)