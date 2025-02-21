from tatoebator.anki_db_interface import AnkiObjectIdRegistry, FieldPointer

AnkiObjectIdRegistry.my_default().save()
print(jjsj)

a = AnkiObjectIdRegistry.my_default()
a.save("test.txt")
b = AnkiObjectIdRegistry.load("test.txt")
print(b)
print(b._jsonify())
print(b.other_vocab_fields)