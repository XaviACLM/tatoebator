from tatoebator.language_processing import DefinitionFetcher

definition_fetcher = DefinitionFetcher()

print(definition_fetcher.get_definitions("はい"))

print(jjsj)

from tatoebator.language_processing.online_dictionaries import TanoshiiDictionary, JishoDictionary, WeblioDictionary

tanoshii_dict = TanoshiiDictionary()
jisho_dict = JishoDictionary()
weblio_dict = WeblioDictionary()

#print(tanoshii_dict.get_definitions("雷撃"))

words = ["はい","いいえ","お願いします","すみません","ごめんなさい","おはよう","こんばんは","さようなら",
             "お休みなさい","元気","名前","友達","家族","学校","先生","学生","本","ペン","紙","水","食べ物","飲み物","お茶","コーヒー",
             "牛乳","パン","米","魚","肉","野菜","果物","りんご","バナナ","猫","犬","鳥","車","電車","バス","自転車","空","太陽",
             "月","星","雨","雪","風","山","川","海","花","木","森","家","部屋","ドア","窓","椅子","机","ベッド","服","靴","帽子",
             "時計","電話","テレビ","音楽","映画","写真","手紙","仕事","休み","旅行","お金","時間","今日","明日","昨日","今","後で",
             "ここ","そこ","あそこ","どこ","誰","何","なぜ","どうやって","いくら","大きい","小さい","新しい","古い","良い","悪い",
             "暑い","寒い","楽しい","悲しい","忙しい","簡単","難しい","近い","遠い","多い","少ない"]


for word in words:
    print(tanoshii_dict.get_definitions(word))
    print(jisho_dict.get_definitions(word))
    print(weblio_dict.get_definitions(word))
    print("\n"*3)