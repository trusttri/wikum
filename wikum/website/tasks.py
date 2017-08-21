from __future__ import absolute_import
from celery import shared_task, current_task
from celery.exceptions import Ignore
from website.import_data import get_source, get_article, get_disqus_posts,\
    get_reddit_posts, count_replies, get_wiki_talk_posts
from django.db import connection
import json

@shared_task()
def import_article(url):
    connection.close()
    
    source = get_source(url)
    if source:
        article = get_article(url, source, 0)
        if article:
            posts = article.comment_set
            total_count = 0
            
            if posts.count() == 0:
                if article.source.source_name == "The Atlantic":
                    get_disqus_posts(article, current_task, total_count)
                    
                elif article.source.source_name == "Reddit":
                    get_reddit_posts(article, current_task, total_count)
                    
                elif article.source.source_name == "Wikipedia Talk Page":
                    get_wiki_talk_posts(article, current_task, total_count)
                    
                article.comment_num = article.comment_set.count()
                article.save()
                print article
                count_replies(article)
        else:
            return 'FAILURE-ARTICLE'
    else:
        return 'FAILURE-SOURCE'
        
@shared_task()
def dump_found_rfcs(file_name):
    _FILE_PATH = "C:/Users/Jane Im/Desktop/rfc_links/noticeboards/"
    file_name = _FILE_PATH + file_name
    with open(file_name) as file:
        [archive_rfcs] = json.load(file)
    for archive_num, rfcs in archive_rfcs.items():
        for section_idx, url in rfcs.items():
            print url

            import_article(url)

            # source = get_source(url)
            # if source.source_name == "Wikipedia Talk Page":
            #     article = get_article(url, source, 0)
            #     print 'new article'
            #     print article
            #     if article:
            #         posts = article.comment_set
            #         total_count = 0
            #
            #         if posts.count() == 0:
            #             get_wiki_talk_posts(article, current_task, total_count)
            #             article.comment_num = article.comment_set.count()
            #             article.save()
            #             count_replies(article)

@shared_task()
def dump_all_found_rfcs(file_name):
    _FILE_PATH = "C:/Users/Jane Im/Desktop/rfc_links/noticeboards/"
    file_name = _FILE_PATH + file_name
    with open(file_name) as file:
        [archive_rfcs] = json.load(file)
    print 'rfc here'
    print archive_rfcs
    for section_idx, url in archive_rfcs.items():
        print url

        import_article(url)