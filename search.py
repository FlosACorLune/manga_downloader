# https://api.cdnlibs.org/api/manga?fields[]=rate_avg&fields[]=rate&fields[]=releaseDate&q=%D0%BF%D1%80%D0%B8%D0%BD%D1%86&site_id[]=1 - mangalib. можно в конце вписать &limit=10 что бы увидеть только часть а не фулл JSON


# {"extensions":{"persistedQuery":{"sha256Hash":"e64937b4fc9c921c2141f2995473161bed921c75855c5de934752392175936bc","version":1}},"operationName":"search","variables":{"query":"принце","type":"MANGA"}} - senkuro JSON

# https://mangabuff.ru/search/suggestions?q=%D0%BF%D1%80%D0%B8%D0%BD%D1%86 - mangabuff. Добавить фильтр что если перед названием тайтла есть слово 'Карточки' или в slug есть karti- то фильтровать их(решает пользователь) поскольку такие тайтлы были удалены главы JSON

# https://mangahub.cc/search?q=%D0%BF%D1%80%D0%B8%D0%BD%D1%86 - mangahubcc. HTML


"""
Docstring for search
вместо q=%... просто вписывать напрямую слово на рус или другом языке посколько это браузер преобразует в utf-8 а там ру нету поэтому и такое происходит
"""

