import utils, config
import mangabuff, mangahub

#добавить парсинг продолжается ли это или нет работает во всех кроме mangahub.live 
#перерабоать mangabuff.ru и добавить парсинг состояние переводы и состояние татйла
#в мангалиб остоит учитывать что иногда есть тайтл/перевод - завершен. 
#вывести архивация из мангахаба в общий

def main():
    utils.read_file_mangalist(config.download_directory)
    url_title_names = utils.route_link(config.download_directory)

    if 'mangahub.live' in url_title_names:
        mangahub.init(url_title_names['mangahub.live'])
    
    if 'mangabuff.ru' in url_title_names:
        mangabuff.init(url_title_names['mangabuff.ru'])

    return
    if 'mangalib.me' in url_title_names:
        mangabuff_v1M.init(url_title_names['mangalib.me'])

    if 'remanga.org' in url_title_names:
        mangabuff_v1M.init(url_title_names['remanga.org'])
    return

#if __name__ == "__main__":
main()