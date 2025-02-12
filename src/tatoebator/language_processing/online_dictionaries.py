import requests
from bs4 import BeautifulSoup

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
    content_elem = soup.find('div', id='cncontentbody')
    decider_elem = content_elem.contents[1]
    if decider_elem.name == 'form':
        for elem in decider_elem.find_all('div', class_='vocabulary'):
            word_elem = elem.find('span', class_='copyable')
            found_word = "".join([elem.text for elem in word_elem.find_all('rb')])
            if not found_word: found_word = word_elem.text
            if word != found_word: continue
            break  # grab the first match (immediate nonetype exception otherwise)

        text = "\n".join([ol_elem.text[1:-1] for ol_elem in elem.find_all('ol')])
        text = "- " + text.replace("\n", "\n- ")
        if "\n" not in text: text = text[2:]

        return text

    elif decider_elem.name == 'div':
        # jp_elem = decider_elem.find('span', class_='copyable')
        # jp_text = "".join([elem.text for elem in jp_elem.find_all('rb')])
        text = "\n".join([ol_elem.text[1:-1] for ol_elem in decider_elem.find_all('ol')])
        text = "- " + text.replace("\n", "\n- ")
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
    # 29??
    text = "\n- ".join([elem.text[29:] for elem in table_elem.find_all('p', class_='wdntTCLJ')])
    if "\n" in text: text = "- " + text
    return text
