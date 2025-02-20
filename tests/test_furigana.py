from tatoebator.language_processing import add_furigana_plaintext

texts=["自由になるのは大変だろう",
       "自由になるのは大変だろう\n",
       "\n自由になるのは大変だろう",
       "\n自由になるのは大変だろう\n",
       ]


for text in texts:
    print(add_furigana_plaintext(text))