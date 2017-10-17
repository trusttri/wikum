from website.models import Article, Source, CommentAuthor, Comment, History, Tag, OpenComment, CloseComment, MetaComment
from wikum.settings import DISQUS_API_KEY
import urllib2
import json
import praw
import datetime
import re
import wikichatter.signatureutils as su
import json
import filters
from django.db.models import Q

USER_AGENT = "website:Wikum:v1.0.0 (by /u/smileyamers)"

THREAD_CALL = 'http://disqus.com/api/3.0/threads/list.json?api_key=%s&forum=%s&thread=link:%s'
COMMENTS_CALL = 'https://disqus.com/api/3.0/threads/listPosts.json?api_key=%s&thread=%s'

_CLOSE_CHECK_WORDS = [r'{{(atop|consensus|Archive(-?)( ?)(top|bottom)|Discussion( ?)top|(closed.*?)?rfc top)', r'\|result=', r"={2,3}( )?Clos(e|ing)( comment(s?)|( RFC)?)( )?={2,3}" , 'The following discussion is an archived discussion of the proposal' , 'A summary of the debate may be found at the bottom of the discussion', 'A summary of the conclusions reached follows']
_CLOSE_COMMENT_CHECK_RE = re.compile(r'|'.join(_CLOSE_CHECK_WORDS), re.IGNORECASE|re.DOTALL)
_CLOSE_COMMENT_KEYWORDS =  [r'{{(atop|consensus|Archive(-?)( ?)top|Discussion( ?)top|(closed.*?)?rfc top)', r'\|result=', r"={2,3}( )?Clos(e|ing)( comment(s?)|( RFC)?)( )?={2,3}" , 'The following discussion is an archived discussion of the proposal' , 'A summary of the debate may be found at the bottom of the discussion', 'A summary of the conclusions reached follows']
_CLOSE_COMMENT_RE = re.compile(r'|'.join(_CLOSE_COMMENT_KEYWORDS), re.IGNORECASE|re.DOTALL)


_rfc_format = r"(_)*rfc(s)?(_)*|(_)*Request(s)?(_)*for(_)*Comment(s)?(_)*"
_rfc_key = re.compile(_rfc_format, re.I)

_talk_link_re = re.compile(r'|'.join(["\[https?://en.wikipedia.org/wiki/.*?\]", "\[\[.*?:\]\]"]))

#exclude WP:RFC
_WIKI_TEMPLATE_RFC_RE = r"\[\[[^\]]*?((rfc(s)?)|(Request(s)?(_| )*for(_| )*Comment(s)?)).*?\]\]"
_HTTPS_RFC_RE = r"https?://en.wikipedia.org/wiki/.*?(rfc(s)?)|(Request(s)?(_)*for(_)*Comment(s)?).*"
_FYI_RE = r"{{FYI\|Pointer to relevant discussion elsewhere.}}|{{FYI}}|{{FYI\|"

_pointer_re = re.compile(r'|'.join([_WIKI_TEMPLATE_RFC_RE, _HTTPS_RFC_RE, _FYI_RE]), re.IGNORECASE)

_rfc_tag_re = re.compile(r'({{rfc)|(The following discussion is closed and should not be)|({{Archive top)', re.I)

"""
DIVIDING RFCS
"""
# step 1 if the "candidate" contains the below, it's definitely an RfC
# won't be much help though
_rfc_tag_re = re.compile(r'{{rfc', re.I)

_definite_rfc_re = [_rfc_tag_re, _CLOSE_COMMENT_RE]



#step 2-1
_inner_link_template = r"\[\[[^\]]*?((rfcs?)|(Requests?(_| )*for(_| )*Comments?)).*?\]\]"
_inner1 = re.compile(r"\[\[[^\]]*?rfcs?.*?\]\]", re.I)
_inner2 = re.compile(r"\[\[[^\]]*?Requests? *for *Comments?.*?\]\]", re.I)
_inner3 = re.compile(r"\[\[[^\]]*?Requests?_*for_*Comments?.*?\]\]", re.I)
_inner_link_pointer_re = re.compile(_inner_link_template, re.IGNORECASE)

exclude_rfc_pages = [ r"\[\[(Wikipedia|WP):RFC(\|[^\]]*)?\]\]", r"\[\[(Wikipedia|WP):RFC/U(\|[^\]]*)?\]\]", r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment(#.*?)(\|[^\]]*)?\]\]",
                      r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/User( |_)*conduct[^\]]*\]\]", r"\[\[(Wikipedia|WP):ANRFC(\|[^\]]*)?\]\]",
                      r"\[\[(Wikipedia|WP):Administrators%27_noticeboard(\|[^\]]*)?\]\]",r"\[\[(Wikipedia|WP):AN(\|[^\]]*)?\]\]", r"\[\[Wikipedia:Requests_for_comment/User_names/Archive(\|[^\]]*)?\]\]"
                      r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/All(#.*?)(\|[^\]]*)?\]\]", r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment(\|[^\]]*)?\]\]",
                      r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/Maths,( |_)*science,( |_)*and( |_)*technology(\|[^\]]*)?\]\]",
                      r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/Biographies(\|[^\]]*)?\]\]",  r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/Economy,( |_)*trade,( |_)*and( |_)*companies(\|[^\]]*)?\]\]",
                      r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/History( |_)*and( |_)*geography(\|[^\]]*)?\]\]",  r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/Language( |_)*and( |_)*linguistics(\|[^\]]*)?\]\]",
                      r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/Media,( |_)*the arts,( |_)*and( |_)*architecture(\|[^\]]*)?\]\]",  r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/Politics,( |_)*government,( |_)*and( |_)*law(\|[^\]]*)?\]\]",
                      r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/Religion( |_)*and( |_)*philosophy(\|[^\]]*)?\]\]", r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/Society,( |_)*sports,( |_)*and( |_)*culture(\|[^\]]*)?\]\]",
                      r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/Wikipedia( |_)*style( |_)*and( |_)*naming(\|[^\]]*)?\]\]", r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/Wikipedia( |_)*policies( |_)*and( |_)*guidelines(\|[^\]]*)?\]\]",
                      r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/WikiProjects( |_)*and( |_)*collaborations(\|[^\]]*)?\]\]", r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/Wikipedia( |_)*technical( |_)*issues( |_)*and( |_)*templates(\|[^\]]*)?\]\]",
                      r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/Wikipedia( |_)*proposals(\|[^\]]*)?\]\]", r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/Unsorted(\|[^\]]*)?\]\]",
                      r"\[\[(Wikipedia|WP):Requests?( |_)*for( |_)*comment/ Request_board(#.*?)(\|[^\]]*)?\]\]"]
exclude_rfc_compiled_regex = [re.compile(ex, re.I) for ex in exclude_rfc_pages]

_wiki_header = "//en.wikipedia.org/wiki/"
_rfc_https = ["RFC", "Wikipedia:Requests_for_comment","Wikipedia:Requests_for_comment/All", "Wikipedia:Requests_for_comment/User_names"
                "Wikipedia:Requests_for_comment/Biographies", "Wikipedia:Requests_for_comment/Economy,_trade,_and_companies",
                "Wikipedia:Requests_for_comment/History_and_geography","Wikipedia:Requests_for_comment/Language_and_linguistics",
                "Wikipedia:Requests_for_comment/Maths,_science,_and_technology", "Wikipedia:Requests_for_comment/Media,_the_arts,_and_architecture",
                "Wikipedia:Requests_for_comment/Politics,_government,_and_law", "Wikipedia:Requests_for_comment/Religion_and_philosophy",
                "Wikipedia:Requests_for_comment/Society,_sports,_and_culture", "Wikipedia:Requests_for_comment/Wikipedia_style_and_naming",
                "Wikipedia:Requests_for_comment/Wikipedia_policies_and_guidelines", "Wikipedia:Requests_for_comment/WikiProjects_and_collaborations",
                "Wikipedia:Requests_for_comment/Wikipedia_technical_issues_and_templates", "Wikipedia:Requests_for_comment/Wikipedia_proposals",
                "Wikipedia:Requests_for_comment/Unsorted", "Wikipedia:Requests_for_comment/Policies", "Wikipedia:Requests_for_comment/Politics",
                "Wikipedia:Requests_for_comment/Society_and_law", "Wikipedia:Requests_for_comment/User_conduct", "Wikipedia:Requests_for_comment/User_names",
                "Wikipedia:Requests_for_comment/Article_RfC_example", "Wikipedia:Requests_for_comment/Request_board", "Wikipedia:Requests_for_comment/Art%2C_architecture%2C_literature_and_media"
                ]
exclude_rfc_https = [_wiki_header + pattern for pattern in _rfc_https]

_FYI_RE = r"{{FYI\|Pointer to relevant discussion elsewhere.}}|{{FYI}}|{{FYI\|"

def load_json(file_path):
    with open(file_path) as file:
        return json.load(file)

def fix_doubled(pro_dict):
    fixed_dict = {}
    for id, dictionary in pro_dict.items():
        for iid, val in dictionary.items():
            fixed_dict[id] = val
    return fixed_dict

def fix_liwc(title):
    #ten
    path = "E:/amy/inputs/" + title + "_dict_article_result.json"
    with open(path) as file:
        pro_dict = json.load(file)
    fixed_dict = fix_doubled(pro_dict)
    with open("E:/amy/inputs/" + "fixed_" + title + "_dict_article_result.json", "w") as file:
        json.dump(fixed_dict, file)



def get_csv_dict():
    # number of participants
    with open("E:/amy/inputs/num_participants.json") as file:
        num_participants_dict = json.load(file)
    # word count dict
    with open("E:/amy/inputs/word_count.json") as file:
        word_count_dict = json.load(file)
    #reply level
    avg_reply_level = load_json("E:/amy/inputs/avg_reply_level.json")
    # reciprocity
    weighted_reciprocity = load_json("E:/amy/inputs/weighted_reciprocity.json")

    # edit counts
    with open("E:/amy/inputs/rough_expertise_edit_counts.json") as file:
        rough_edit_count_dict = json.load(file)
    # pure edit counts
    pure_edit_counts = load_json("E:/amy/inputs/pure_expertise_edit_counts.json")
    # time since join until comment
    expertise_since_joined = load_json("E:/amy/inputs/expertise_joined_since.json")


    # positive
    pos_dict = load_json("E:/amy/inputs/new_positive-liwc_dict_article_result.json")
    # negative
    neg_dict = load_json("E:/amy/inputs/new_negative-liwc_dict_article_result.json")
    # anger
    anger_dict = load_json("E:/amy/inputs/new_anger_dict_article_result.json")
    # hostility
    host_dict = load_json("E:/amy/inputs/new_hostility_dict_article_result.json")
    # certainty
    certainty_dict = load_json("E:/amy/inputs/new_certain_dict_article_result.json")
    # tentative
    ten_dict = load_json("E:/amy/inputs/new_tentative_dict_article_result.json")

    # support
    support_dict = load_json("E:/amy/inputs/nonfiltered_support.json")

    """output"""
    # closed dict
    closed_dict = {True:1, False:0}
    # closing length
    closing_length_char = load_json("E:/amy/outputs/wrong_filtered_closing_length.json")
    # closing num words
    closing_word_count = load_json("E:/amy/outputs/closing_word_count.json")
    #running period
    running_period = load_json("E:/amy/outputs/wrong_filtered_closing_period.json")
    #closing period
    closing_period = load_json("E:/amy/outputs/close_time_since_last_comment.json")
    #closing_positive
    closing_pos = load_json("E:/amy/outputs/new_positive-liwc_closing_tone.json")
    #closing_negative
    closing_neg = load_json("E:/amy/outputs/new_negative-liwc_closing_tone.json")
    #closing_anger
    closing_anger = load_json("E:/amy/outputs/new_anger_closing_tone.json")
    #closing_hostility
    closing_hos = load_json("E:/amy/outputs/new_hostility_closing_tone.json")
    #closing_certainty
    closing_cer = load_json("E:/amy/outputs/new_certain_closing_tone.json")
    #closing_tentativeness
    closing_ten = load_json("E:/amy/outputs/new_tentative_closing_tone.json")

    csv_dict = {}
    articles = Article.objects.all()
    for article in articles:
        article_id = article.id
        str_aid = str(article_id)
        csv_dict[article.id] = {
            "id":article.id,
            "number_of_comments":article.comment_num,
            "number_of_participants":num_participants_dict[str_aid],
            "number_of_words":word_count_dict[str_aid],
            "avg_depth_of_thread":avg_reply_level[str_aid],
            "reciprocity":0,
            "rough_avg_participant_editcount":rough_edit_count_dict[str_aid],
            "pure_avg_participant_editcount":0, #at bottom
            "avg_participant_joined_period":0, #at bottom
            "rfc_positive":pos_dict[str_aid],
            "rfc_negative":neg_dict[str_aid],
            "rfc_anger":anger_dict[str_aid],
            "rfc_hostility":host_dict[str_aid],
            "rfc_certainty":certainty_dict[str_aid],
            "rfc_tentativeness":ten_dict[str_aid],
            "support_ratio":-1,#at bottom
            "oppose_ratio":-1,#at bottom

            "is_closed":closed_dict[article.closed],
            "running_period":-1,#at bottom
            "closing_period":-1,#at bottom
            "closing_letter_count":-1,#at bottom
            "closing_word_count":-1,#at bottom
            "close_positive":-1,
            "close_negative":-1,
            "close_anger":-1,
            "close_hostility":-1,
            "close_certainty":-1,
            "close_tentative":-1

        }

        #support
        if str_aid in support_dict:
            csv_dict[article.id]["support_ratio"] = support_dict[str_aid]
            csv_dict[article.id]["oppose_ratio"] = 1.0 - support_dict[str_aid]
        if str_aid in expertise_since_joined:
            csv_dict[article.id]["avg_participant_joined_period"] = expertise_since_joined[str_aid]
        if str_aid in pure_edit_counts:
            csv_dict[article.id]["pure_avg_participant_editcount"] = pure_edit_counts[str_aid]
        if str_aid in running_period:
            csv_dict[article.id]["running_period"] = long(running_period[str_aid])
        if str_aid in closing_period:
            csv_dict[article.id]["closing_period"] = closing_period[str_aid]
        if str_aid in closing_length_char:
            csv_dict[article.id]["closing_letter_count"] = long(closing_length_char[str_aid])
        if str_aid in closing_word_count:
            csv_dict[article.id]["closing_word_count"] = closing_word_count[str_aid]
        if str_aid in weighted_reciprocity:
            csv_dict[article.id]["reciprocity"] = weighted_reciprocity[str_aid]
        if str_aid in closing_pos:
            csv_dict[article.id]["close_positive"] = closing_pos[str_aid]
        if str_aid in closing_neg:
            csv_dict[article.id]["close_negative"] = closing_neg[str_aid]
        if str_aid in closing_anger:
            csv_dict[article.id]["close_anger"] = closing_anger[str_aid]
        if str_aid in closing_hos:
            csv_dict[article.id]["close_hostility"] = closing_hos[str_aid]
        if str_aid in closing_cer:
            csv_dict[article.id]["close_certainty"] = closing_cer[str_aid]
        if str_aid in closing_ten:
            csv_dict[article.id]["close_tentative"] = closing_ten[str_aid]

    with open("E:/amy/csv_dict.json", "w") as file:
        json.dump(csv_dict, file)


def get_wierd_closing_tone(title):
    # to get more precise closing tones!
    closing_writing_valid = load_json("E:/amy/outputs/wrong_filtered_closing_length.json")
    tone_dict = load_json("E:/LIWC results/"+title+"_dict_comments_result.json")
    close_tones = {}

    for article_id in closing_writing_valid:
        close_comments = CloseComment.objects.filter(article_id= article_id)
        print article_id
        tone_sum = 0.0
        c_count = 0
        for cc in close_comments:
            comment = cc.comment
            str_cid = str(comment.id)
            text = comment.text
            if len(text)>1:
                c_count += 1

            actual_dict = tone_dict[str(article_id)][str(article_id)]
            if str_cid in actual_dict:
                tone = actual_dict[str_cid]
                tone_sum += tone
                print tone
        if c_count > 0:
            close_tones[article_id] = tone_sum/c_count
        else:
            close_tones[article_id] = 0
    with open("E:/amy/outputs/"+title+"_closing_tone.json", "w") as file:
        json.dump(close_tones, file)

def get_closing_tone(title):
    # to get more precise closing tones!
    closing_writing_valid = load_json("E:/amy/outputs/wrong_filtered_closing_length.json")
    tone_dict = load_json("E:/amy/inputs/"+title+"_dict_comments_result.json")
    close_tones = {}
    for article_id in closing_writing_valid:
        close_comments = CloseComment.objects.filter(article_id= article_id)
        print article_id
        tone_sum = 0.0
        c_count = 0
        comment_score_dict = tone_dict[str(article_id)]
        for cc in close_comments:
            comment = cc.comment
            str_cid = str(comment.id)
            tone = comment_score_dict[str_cid]
            tone_sum += tone
            c_count += 1
            print tone
        if c_count > 0:
            close_tones[article_id] = (1.0*tone_sum)/c_count
        else:
            close_tones[article_id] = 0
    with open("E:/amy/outputs/"+title+"_closing_tone.json", "w") as file:
        json.dump(close_tones, file)


def get_closing_words():
    closing_writing_valid = load_json("E:/amy/outputs/wrong_filtered_closing_length.json")
    closing_word_count = {}
    for article_id in closing_writing_valid:
        print article_id
        close_comments = CloseComment.objects.filter(article_id= article_id)
        word_count = 0
        for cc in close_comments:
            c = cc.comment
            comment_text = c.text
            comment_text = re.sub(r"\[\[.*?\]\]", "", comment_text)
            wordlist = re.sub("[^\w]", " ", comment_text).split()
            word_count += len(wordlist)
        closing_word_count[article_id] = word_count
    with open("E:/amy/outputs/closing_word_count.json", "w") as file:
        json.dump(closing_word_count, file)

def get_avg_participants():
    articles = Article.objects.all()
    participants_num = {}
    for article in articles:
        article_id = article.id
        comments = Comment.objects.filter(article=article)
        participants = set([c.author_id for c in comments])
        participants_num[article_id] = len(participants)
    with open("E:/amy/inputs/num_participants.json", "w") as file:
        json.dump(participants_num, file)

def get_pure_avg_expertise_participants():
    articles = Article.objects.all()
    expertise_edit_counts = {}

    for article in articles:
        print article.id
        comments = Comment.objects.filter(article=article)
        authors = set([c.author for c in comments])

        edit_count_expertise = 0
        edit_count_num = 0

        for author in authors:
            edit_count = author.edit_count
            if author.disqus_id is not None:
                edit_count_expertise += edit_count
                edit_count_num += 1
        if edit_count_num != 0:
            expertise_edit_counts[article.id] = 1.0 * edit_count_expertise / edit_count_num
    with open("E:/pure_expertise_edit_counts.json", "w") as file:
        json.dump(expertise_edit_counts, file)

def get_sum_editcounts():
    articles = Article.objects.all()
    expertise_edit_counts = {}

    for article in articles:
        print article.id
        comments = Comment.objects.filter(article=article)
        authors = set([c.author for c in comments])

        edit_count_expertise = 0
        edit_count_num = 0

        for author in authors:
            edit_count = author.edit_count
            edit_count_expertise += edit_count

        expertise_edit_counts[article.id] = edit_count_expertise
    with open("C:/Users/Jane Im/sum_expertise_edit_counts.json", "w") as file:
        json.dump(expertise_edit_counts, file)


def get_avg_expertise_participants():
    articles = Article.objects.all()
    expertise_edit_counts = {}

    for article in articles:
        print article.id
        comments = Comment.objects.filter(article=article)
        authors = set([c.author for c in comments])

        edit_count_expertise = 0
        edit_count_num = 0

        for author in authors:
            edit_count = author.edit_count
            if edit_count is not None:
                edit_count_expertise += edit_count
                edit_count_num += 1
        if edit_count_num != 0:
            expertise_edit_counts[article.id] = 1.0 * edit_count_expertise / edit_count_num
    with open("E:/expertise_edit_counts.json", "w") as file:
        json.dump(expertise_edit_counts, file)


def get_avg_timeexperience_participants():
    articles = Article.objects.all()
    expertise_joined_at = {}

    for article in articles:
        print article.id
        comments = Comment.objects.filter(article = article)
        authors = set([c.author for c in comments])

        joined_at_expertise = datetime.timedelta(0, 0)
        # the unique number of participants that can be calculated of getting lapse
        join_count_num = 0

        for author in authors:
            # time passed since participation
            joined_at = author.joined_at
            if joined_at is not None:
                comments = Comment.objects.filter(author = author, article = article, created_at__isnull=False)
                if len(comments) > 0:
                    join_count_num += 1
                    # each author's number of comment track
                    author_comment_count = 0
                    each_joined_at_expertise = datetime.timedelta(0, 0)
                    for comment in comments:
                        created_at = comment.created_at
                        if created_at is not None:
                            author_comment_count += 1
                            each_joined_at_expertise += (created_at - joined_at)
                    if author_comment_count != 0:
                        each_joined_at_expertise /= author_comment_count
                joined_at_expertise += each_joined_at_expertise

        if join_count_num != 0:
            expertise_joined_at[article.id] = (joined_at_expertise / join_count_num).total_seconds()

    with open("E:/expertise_joined_at.json", "w") as file:
        json.dump(expertise_joined_at, file)


def get_avg_unweighted_timeexperience_participants():
    articles = Article.objects.all()
    expertise_joined_at = {}

    for article in articles:
        print article.id
        comments = Comment.objects.filter(article = article)
        authors = set([c.author for c in comments])

        joined_at_expertise = datetime.timedelta(0, 0)
        # the unique number of participants that can be calculated of getting lapse
        join_count_num = 0

        for author in authors:
            # time passed since participation
            joined_at = author.joined_at
            if joined_at is not None:
                comments = Comment.objects.filter(author = author, article = article, created_at__isnull=False)
                if len(comments) > 0:
                    join_count_num += 1
                    # each author's number of comment track
                    author_comment_count = 0
                    each_joined_at_expertise = datetime.timedelta(0, 0)
                    for comment in comments:
                        created_at = comment.created_at
                        if created_at is not None:
                            author_comment_count += 1
                            each_joined_at_expertise += (created_at - joined_at)
                    if author_comment_count != 0:
                        each_joined_at_expertise /= author_comment_count
                joined_at_expertise += each_joined_at_expertise

        if join_count_num != 0:
            expertise_joined_at[article.id] = (joined_at_expertise / join_count_num).total_seconds()

    with open("E:/expertise_joined_at.json", "w") as file:
        json.dump(expertise_joined_at, file)

def get_length_of_closing():
    articles = Article.objects.all()


def get_word_count():
    articles = Article.objects.all()
    word_counts = {}
    for article in articles:
        print article.id
        word_count = 0
        comments = Comment.objects.filter(article=article)
        for comment in comments:
            comment_text = comment.text
            comment_text = re.sub(r"\[\[.*?\]\]", "", comment_text)
            wordlist = re.sub("[^\w]", " ",  comment_text).split()
            word_count += len(wordlist)
        word_counts[article.id] = word_count
    with open("E:/word_count.json", "w") as file:
        json.dump(word_counts, file)

def get_avg_reply_level():
    articles = Article.objects.all()
    avg_reply_levels = {}
    for article in articles:
        print article.id
        total_reply_level = 0
        comments = Comment.objects.filter(article=article)
        count_comment = article.comment_set.count()
        for comment in comments:
            total_reply_level += comment.reply_level

        avg_reply_level = (1.0*total_reply_level)/count_comment
        avg_reply_levels[article.id] = avg_reply_level

    with open("C:/Users/Jane Im/avg_reply_level.json", "w") as file:
        json.dump(avg_reply_levels, file)

    return avg_reply_levels


"""
Script for getting the article ids of the 2034 previous RfCs
"""

def get_liwc_dict(name):
    file_path = "C:/Users/Jane Im/Documents/CHI_rfc_analysis/LICW_dictionaries/" + name + ".txt"
    with open(file_path) as f:
        content = f.readlines()

    content = [x.strip() for x in content]
    refined = []
    for c in content:
        tab_splits = c.split("\t")
        refined += [t.strip() for t in tab_splits]
    return refined


def search_pattern(keywords, comment_text):
    count = 0
    for keyword in keywords:
        pattern = re.compile(keyword, re.I)
        if pattern.search(comment_text):
            count += 1

    comment_text = re.sub(r"\[\[.*?\]\]", "", comment_text)
    comment_text = re.sub("UTC", "", comment_text)
    wordlist = re.sub("[^\w]", " ", comment_text).split()
    total_words = len(wordlist)
    if total_words > 0:
        return (1.0*count)/total_words
    return None


def get_all_articles_score(title):
    keywords = get_liwc_dict(title)
    articles = Article.objects.all()
    all_article_scores = {}
    all_comment_scores = {}

    for article in articles:
        tentative_article, tentative_comments = get_tentative_score(keywords, article)

        all_article_scores[article.id] = tentative_article
        all_comment_scores[article.id] = tentative_comments

    with open("C:/Users/Jane Im/new_"+title+"_dict_article_result.json", 'w') as outfile:
        json.dump([all_article_scores], outfile)

    with open("C:/Users/Jane Im/new_"+title+"_dict_comments_result.json", 'w') as outfile:
        json.dump([all_comment_scores], outfile)


def get_tentative_score(keywords, article):
    tentative_comments = {}
    article_id = article.id

    comments = Comment.objects.filter(article = article)
    print article_id

    for c in comments:
        comment_id = c.id
        comment_text = c.text
        # returns none when the comment has no text
        score = search_pattern(keywords, comment_text)
        if score is not None:
            tentative_comments[comment_id] = score
    total_considered_comments = len(tentative_comments)

    if total_considered_comments == 0:
        return  0, tentative_comments
    else:
        article_level = (1.0*sum(tentative_comments.values()))/total_considered_comments
        print article_level
        return article_level , tentative_comments


def get_previious_stored_rfcs():
    urls = set()
    articles = Article.objects.all()
    for article in articles:
        if article.id < 2039:
            urls.add(article.url)
    file_name = "C:\Users\Jane Im\previous_rfcs.json"
    with open(file_name, 'w') as outfile:
        json.dump([urls], outfile)

def get_time_between_last_comment_close(closed_rfcs):
    time_lapse = {}
    for article_id in closed_rfcs:
        print article_id
        close_comment_batch = CloseComment.objects.filter(article_id = article_id)
        close_comment_ids = [c.comment_id for c in close_comment_batch]
        close_comment = Comment.objects.filter(article_id = article_id, id__in=close_comment_ids, created_at__isnull=False).order_by('created_at').first()

        if close_comment is not None:
            last_comment_candidates = Comment.objects.filter(article_id = article_id, created_at__isnull=False).exclude(id__in=close_comment_ids)
            if last_comment_candidates is not None:
                filtered_candidates = last_comment_candidates.filter(created_at__lt=close_comment.created_at)
                if filtered_candidates is not None:
                    last_comment = filtered_candidates.order_by('-created_at').first()
                # last_comment = last_comment_candidates.order_by('-created_at').first()
                    if last_comment is not None:
                        timelapse = (close_comment.created_at - last_comment.created_at)
                        print timelapse
                        print close_comment.created_at
                        print last_comment.created_at
                        time_lapse[article_id] = timelapse
    return time_lapse


def get_rfcs_at():
    articles = Article.objects.all()

    # first get all the pages
    at_rfcs = {}
    for article in articles:
        url = article.url
        at_re = re.compile(".*?rfcs?_at.*", re.I)
        if at_re.search(url):
            at_rfcs[article.id] = url

    file_name = "C:/Users/Jane Im/Desktop/filter/at_Rfcs.json"
    with open(file_name, 'w') as outfile:
        json.dump([at_rfcs], outfile)
    print len(at_rfcs)

def get_sections_from_same_page():
    articles = Article.objects.all()

    #first get all the pages
    pages = {}
    for article in articles:
        url = article.url
        if "#" in url:
            page = url.split("#")[0]
            pages[page] = []

    for article in articles:
        url = article.url
        if "#" in url:
            page = url.split("#")[0]
            pages[page].append(url)

    multiple_exists = {}
    for page, urls in pages.items():
        if len(urls) > 1:
            multiple_exists[page] = urls

    file_name = "C:/Users/Jane Im/Desktop/filter/pages.json"
    with open(file_name, 'w') as outfile:
        json.dump([multiple_exists], outfile)
        print len(multiple_exists)


def filter_out_wrong_pages():
    _wikipedia_rfc_re = r"https://en.wikipedia.org/wiki/((Wikipedia)|(WP)):((RfC/)|(Requests?_for_comments?/)).*"
    _rfc_bot_re = r"https://en.wikipedia.org/wiki/.*?rfc.*?bot.*"
    _template_re = r"https://en.wikipedia.org/wiki/Template:.*"
    _rfc_archive_re = r"https://en.wikipedia.org/wiki/Wikipedia_talk:Requests_for_comment/Archive.*"
    _rfc_before_re = r"[a-zA-Z0-9]+rfc"
    _rfc_after_re = r"rfc[a-zA-Z0-9]+"
    _user_re = r"https://en.wikipedia.org/wiki/User.*"
    #
    # _filter_re = re.compile(r"|".join([_wikipedia_rfc_re, _rfc_bot_re, _template_re, _rfc_section_re, _rfc_before_re, _rfc_after_re]), re.I)

    filtered_rfcs = {}
    _filter_re = re.compile(_user_re, re.I)
    articles = Article.objects.all()
    for a in articles:
        url = a.url
        if re.compile(_wikipedia_rfc_re, re.I).search(url):
            filtered_rfcs[a.id] = url
    file_name = "C:/Users/Jane Im/Desktop/filter/invalid_only_rfc_page.json"
    with open(file_name, 'w') as outfile:
        json.dump([filtered_rfcs], outfile)
        print len(filtered_rfcs)

def filter_rfc_with_one_comment():
    valid_rfcs = filters.comment_num_real_rfcs.values()
    one_comment_rfcs = Article.objects.filter(Q(comment_num = 1), Q(candidate_type=0)|Q(candidate_type=1))
    changed = set()
    for a in one_comment_rfcs:
        if a.url not in valid_rfcs:
            a.candidate_type = 2
            a.save()
            changed.add(a.id)
        else:
            # if in valid, chosen ones
            a.candidate_type = 0
            a.save()
    return changed


def check_redundant_rfc_pages():
    articles = Article.objects.all()
    rfcs_having_parents = {}
    rfc_to_id = {}
    for a in articles:
        url = a.url
        if "#" in url:
            page_url = url.split("#")[0]
            try:
                parent_page = Article.objects.get(url=page_url)
                if parent_page:
                    rfcs_having_parents[a.id] = parent_page.url
                    rfc_to_id[a.id] = a.url
            except Exception:
                pass
    file_name = "C:/Users/Jane Im/Desktop/filter/rfcs_having_parents.json"
    with open(file_name, 'w') as outfile:
        json.dump([rfcs_having_parents], outfile)
        print len(rfcs_having_parents)
    with open("C:/Users/Jane Im/Desktop/filter/rfcs_having_parents_id_to_url.json", 'w') as outfile:
        json.dump([rfc_to_id], outfile)
        print len(rfc_to_id)


def is_rfc(text, article):
    filtered_patterns = set()
    # step 1
    for pattern in _definite_rfc_re:
        if pattern.search(text):
            return True, filtered_patterns

    # step 2
    for i in [_inner1, _inner2, _inner3]:
        i_foundall = i.findall(text)
        for link in i_foundall:
            link = link.strip()
            if not any([r.search(link) for r in exclude_rfc_compiled_regex]):
                filtered_patterns.add(link)

    for e in [_exter1, _exter2]:
        e1_foundall = e.findall(text)
        for link in e1_foundall:
            link = link.strip()
            link = re.sub("https?://", '', link)
            if link not in exclude_rfc_https:
                filtered_patterns.add(link)

    if len(filtered_patterns) > 0:
        article.candidate_reason = " * ".join(list(filtered_patterns))
        article.save()
        return False , filtered_patterns

    if re.search(_FYI_RE, text):
        return False , filtered_patterns

    return True , filtered_patterns

# step 2-2
_external_link_pointer_re = re.compile(r"//en.wikipedia.org/wiki/[a-zA-Z0-9_:/]*((rfcs?)|(Requests?(_)*for(_)*Comments?))[a-zA-Z0-9_:/]*", re.I)
_exter1 = re.compile(r"//en.wikipedia.org/wiki/[a-zA-Z0-9_:/#]*rfcs?[a-zA-Z0-9_:/]*", re.I)
_exter2 = re.compile(r"//en.wikipedia.org/wiki/[a-zA-Z0-9_:/#]*Requests?_*for_*Comments?[a-zA-Z0-9_:/]*", re.I)


#

# example of wiki link
# [[Talk:Martin Landau#RfC: Is a career image better for the lead.3F]]
# [[Wikipedia talk:Manual of Style/Images/Archive 6|the February 2016 RfC]]
# [[Talk:Family Guy#RfC: Remove "adult" as a descriptor from the opening sentence]]
# [[Talk:2014_Iranian-led_intervention_in_Iraq#RFC:_Military_intervention_against_ISIS_2014_in_Iraq]]
# [[Wikipedia:Requests for comment/Global consensus check:Sports notability guideline|join in the converstion]]

# example of https
# [https://en.wikipedia.org/wiki/Wikipedia:Requests_for_comment/Slrubenstein request for comment]

# relevant pointer
# {{FYI|Pointer to relevant discussion elsewhere.}}
# The rfc is here


# retrieve candidate type
# 1: no link
# 2: link, but no rfc keyword
# 3: link, with rfc keyword
def get_candidate_type():
    articles = Article.objects.all()
    all_filtered_reasons = set()
    for article in articles:
        # get the first comment
        print article.id
        comments = Comment.objects.filter(article_id = article.id).order_by('id')
        first_comment = comments.first()
        first_comment_text = first_comment.text
        article.first_comment = first_comment_text

        # search for link first
        if _talk_link_re.search(first_comment_text):
            article.candidate_type = 1

        rfc_true, filtered_patterns = is_rfc(first_comment_text, article)
        print filtered_patterns
        if not rfc_true:
            article.candidate_type = 2

        all_filtered_reasons = all_filtered_reasons.union(filtered_patterns)

        article.save()
    file_name = "C:/Users/Jane Im/Desktop/filtered_patterns2.json"
    with open(file_name, 'w') as outfile:
        json.dump(list(all_filtered_reasons), outfile)
    return all_filtered_reasons

def get_pointers():

    articles = Article.objects.filter(Q(candidate_type=2)|Q(candidate_type=4))
    all_filtered_reasons = set()

    for article in articles:
        comments = Comment.objects.filter(article_id=article.id).order_by('id')
        first_comment = comments.first()
        first_comment_text = first_comment.text

        rfc_true, filtered_patterns = is_rfc(first_comment_text, article)
        all_filtered_reasons = all_filtered_reasons.union(filtered_patterns)
    file_name = "C:/Users/Jane Im/Desktop/filtered_patterns_9_3.json"
    with open(file_name, 'w') as outfile:
        json.dump(list(all_filtered_reasons), outfile)
    print len(all_filtered_reasons)

def get_all_stored_urls():
    urls = set()
    articles = Article.objects.all()
    for article in articles:
        urls.add(article.url)
    return list(urls)

def get_page_section_from_stored_urls():
    urls = set()
    articles = Article.objects.all()
    for article in articles:
        url = article.url
        if "#" in url:
            section = url.split("#")[-1]
            page = url.replace("#" + section, "")
            urls.add((page, section))
        else:
            urls.add((url, ""))
    return list(urls)

def get_title_sections():
    articles = Article.objects.all()
    titles = set()
    for article in articles:
        title = article.title
        url = article.url
        if "#" in url:
            section = title.split(' - ')[-1]
            page = title.replace(' - ' + section, "")
            titles.add((page, section))
        else:
            titles.add((title, ""))
    return list(titles)


def get_external_links_from_pointers():
    stored_urls = get_all_stored_urls()
    stored_page_sections = get_page_section_from_stored_urls()
    new_urls = set()

    with open("C:/Users/Jane Im/wikum/wikum/website/filtered_patterns.json") as openfile:
        filtered = json.load(openfile)
    external = []
    for text in filtered:
        for e in [_exter1, _exter2]:
            e1_foundall = e.findall(text)
            for link in e1_foundall:
                link = link.strip()
                link = re.sub("https?://", '', link)
                if link not in exclude_rfc_https:
                    external.append(link)

    for link in external:
        cleansed_url =  urllib2.unquote("https://" + link)
        if "#" not in cleansed_url:
            if cleansed_url not in stored_urls:
                new_urls.add(cleansed_url)
        else:
            #check with page part and section part of url
            section = cleansed_url.split("#")[-1]
            page = cleansed_url.replace("#" + section, "")
            stored = False
            for stored_p, stored_s in stored_page_sections:
                if (page in stored_p or stored_p in page)and section == stored_s:
                    stored = True
                    break
            if not stored:
                new_urls.add(cleansed_url)
    print len(new_urls)
    file_name = "C:/Users/Jane Im/Desktop/new_outlinks.json"
    with open(file_name, 'w') as outfile:
        json.dump(list(new_urls), outfile)

def get_inner_links_from_pointers():
    stored_urls = get_all_stored_urls()
    stored_page_sections = get_page_section_from_stored_urls()
    stored_titles = get_title_sections()
    new_urls = set()
    found = set()
    with open("C:/Users/Jane Im/wikum/wikum/website/filtered_patterns.json") as openfile:
        filtered = json.load(openfile)

    internal = set()
    for text in filtered:
        for i in [_inner1, _inner2, _inner3]:
            i_foundall = i.findall(text)
            for link in i_foundall:
                link = link.strip()
                if not any([r.search(link) for r in exclude_rfc_compiled_regex]):
                    link = link.split("|")[0]
                    link = re.sub(r"(\[\[)|(\]\])", "", link)
                    internal.add(link)

    print "INTERNAL"
    print len(internal)
    for link in list(internal):
        whole_url = "https://en.wikipedia.org/wiki/" + link.replace(" ", "_")
        if "#" not in link:
            # if it's a url format
            if "_" in link:
                if whole_url not in stored_urls:
                    new_urls.add(whole_url)
                else:
                    found.add(whole_url)
            # if it's a title format
            else:
                stored = False
                for stored_p, stored_s in stored_titles:
                    if stored_p == link:
                        stored = True
                        found.add(whole_url)
                        break
                if not stored:
                    new_urls.add(whole_url) # should later check this out
        else:
            section = link.split("#")[-1]
            page = link.replace("#" + section, "")
            stored = False

            # if it's a url format
            if "_" in link:
                for stored_p, stored_s in stored_page_sections:
                    if (page in stored_p or stored_p in page) and section == stored_s:
                        stored = True
                        found.add(whole_url)
                        break
                if not stored:
                    new_urls.add(whole_url)

            # if it's a title format
            else:
                for stored_p, stored_s in stored_titles:
                    if (page in stored_p or stored_p in page) and section == stored_s:
                        stored = True
                        found.add(whole_url)
                        break
                if not stored:
                    new_urls.add(whole_url)
            #check with page part and section part of url

    print len(new_urls)
    print len(found)
    file_name = "C:/Users/Jane Im/Desktop/new_innerlinks.json"
    with open(file_name, 'w') as outfile:
        json.dump(list(new_urls), outfile)
    file_name = "C:/Users/Jane Im/Desktop/found_innerlinks.json"
    with open(file_name, 'w') as outfile:
        json.dump(list(found), outfile)


def extract_rfcs_from_pointers():
    with open("C:/Users/Jane Im/Desktop/filtered_patterns2.json") as openfile:
        reasons = json.load(openfile)


# for getting number of comments in article
def get_article_num_comments():
    articles = Article.objects.all()
    for article in articles:
        article.comment_num = article.comment_set.count()
        article.save()
    print 'all finished'

# for getting number of replies of all comments
# assume disqus_id of valid comment is not an empty string or none
def get_all_comments_num_replies():
    def count_replies(article):
        comments = Comment.objects.filter(article=article)
        for c in comments:
            if c.disqus_id != '':
                replies = Comment.objects.filter(reply_to_disqus=c.disqus_id, article=article).count()
                c.num_replies = replies
                c.save()

    articles = Article.objects.all()
    for a in articles:
        count_replies(a)

###

### need to do with boundary because the first 2034 were done manually ###
def get_open_comment(boundary):
    articles = Article.objects.all()
    for article in articles:
        # open_comment = OpenComment.obejcts.filter(article_id = article.id)
        # if it's not stored yet
        if article.id > boundary:
            article_comments = Comment.objects.filter(article_id = article.id, created_at__isnull=False).exclude(author_id=13891).order_by('created_at')
            #get the most oldest one
            open_comment = article_comments.first()
            OpenComment.objects.get_or_create(article = article, comment = open_comment, author = open_comment.author)


#### store separately ####
def filter_ads():
    articles = Article.objects.all()
    for a in articles:
        comment_num = a.num_comments
        if comment_num < 3:
            print 'possible candidate of non-RFC'

def get_avg_comment_level():
    avg_comment_dict = {}
    articles = Article.objects.all()
    for a in articles:
        comments = Comment.object.filter(article = a)
        comment_num = len(comments)
        reply_levels = [c.reply_level for c in comments]
        avg_reply_level = 1.0*sum(reply_levels)/comment_num
        avg_comment_dict[a.id] = avg_reply_level
    with open("E:/amy/inputs/avg_reply_level.json", "w") as file:
        json.dump(avg_comment_dict, file)


def get_comment_level_dict():
    articles = Article.objects.all()
    for a in articles:
        article_id = a.id
        print article_id
        # comments = Comment.objects.filter(article_id = article_id, reply_to_disqus__isnull=True)
        comments = Comment.objects.filter(article_id=article_id)
        for comment in comments:
            level = recur_level(comment, article_id, 0)
            comment.reply_level = level
            comment.save()

#the old one
def get_comment_levels():
    articles = Article.objects.all()
    for a in articles:
        article_id = a.id
        print article_id
        comments = Comment.objects.filter(article_id = article_id, reply_to_disqus__isnull=True)
        for comment in comments:
            level = recur_level(comment, article_id, 0)
            comment.reply_level = level
            comment.save()

def recur_level(comment, article_id, level):
    if comment.disqus_id != '':
        replies = Comment.objects.filter(reply_to_disqus=comment.disqus_id, article_id=article_id)
        if len(replies) > 0:
            levels = []
            level += 1
            for r in replies:
                levels.append(recur_level(r, article_id, level))
            return max(levels)
        return level

def fix_author_info(track_unfound):
    authors = CommentAuthor.objects.filter(disqus_id__isnull=True)
    fixed_authors = []
    unfound = load_json("E:/undisqus.json")
    print len(unfound)
    for author in authors:
        if author.username not in unfound:
            print author.username
            from wikitools import wiki, api
            site = wiki.Wiki('https://en.wikipedia.org/w/api.php')
            params = {'action': 'query', 'list': 'users', 'ususers': author.username,
                      'usprop': 'blockinfo|groups|editcount|registration|emailable|gender', 'format': 'json'}

            request = api.APIRequest(site, params)
            result = request.query()
            if 'users' in result['query'] and len(result['query']['users']) > 0:
                user = result['query']['users'][0]
                # try:
                if 'userid' in user:
                    print "imported"
                    if user['registration'] is not None:
                        try:
                            author.joined_at = datetime.datetime.strptime(user['registration'], '%Y-%m-%dT%H:%M:%SZ')

                        except Exception:
                            pass

                    author.edit_count = user['editcount']
                    author.gender = user['gender']
                    author.groups = ','.join(user['groups'])
                    author.is_wikipedia = True
                    # should be the last
                    author.disqus_id = user['userid']
                    author.save()
                    fixed_authors.append(author.username)
                else:
                    unfound.append(author.username)
                    with open("E:/undisqus.json", "w") as file:
                        json.dump(unfound, file)

    with open("E:/fixed_usernames.json", "w") as file:
        json.dump(fixed_authors, file)
    with open("E:/undisqus.json", "w") as file:
        json.dump(track_unfound, file)
    print len(fixed_authors)
    return fixed_authors

            # comment_author = CommentAuthor.objects.create(username=user['name'],
            #                                                       disqus_id=author_id,
            #                                                       joined_at=user['registration'],
            #                                                       edit_count=user['editcount'],
            #                                                       gender=user['gender'],
            #                                                       groups=','.join(user['groups']),
            #                                                       is_wikipedia=True
            #                                                       )
            # except Exception:



def get_deep_replies():
    articles = Article.objects.all()
    for a in articles:
        article_id = a.id
        comments = Comment.objects.filter(article_id = article_id)
        for comment in comments:
            deep_num_replies = recur_replies(comment, article_id)
            comment.deep_num_replies = deep_num_replies
            comment.save()


def recur_replies(comment, article_id):
    total_replies = 0
    if comment.disqus_id != '':
        replies = Comment.objects.filter(reply_to_disqus=comment.disqus_id, article_id=article_id)
        total_replies += replies.count()
        for r in replies:
            total_replies += recur_replies(r, article_id)
    return total_replies


def close_article():
    close_comments = CloseComment.objects.all()
    for cc in close_comments:
        article_id = cc.article_id
        article = Article.objects.get(id=article_id)
        article.closed = True
        article.save()


def fix_timestamp():
    comments = Comment.objects.all()
    for comment in comments:
        comment_text = comment.text
        import wikichatter as wc
        parsed_comments = wc.parse(comment_text.encode('ascii', 'ignore'))['sections'][0]['comments']
        timestamps = []
        for parsed_text in parsed_comments:
            if 'time_stamp' in parsed_text:
                timestamps.append(parsed_text['time_stamp'])
        if len(timestamps)>0:
            timestamp = timestamps[-1]
            formats = ['%H:%M, %d %B %Y (%Z)', '%H:%M, %d %b %Y (%Z)', '%H:%M %b %d, %Y (%Z)']
            for date_format in formats:
                try:
                    time = datetime.datetime.strptime(timestamp, date_format)
                except ValueError:
                    pass
            if time:
                comment.created_at = time
            else:
                comment.created_at = None
            comment.save()


def add_open_comment(url, comment_id):
    article = Article.objects.get(url=url)
    comments = Comment.objects.filter(article_id = article.id)
    comment_ids = [c.id for c in comments]
    existing_open_comment = OpenComment.objects.get(article_id = article.id)
    if existing_open_comment:
        print "deete already existing open comment"
        print existing_open_comment.comment_id
        existing_open_comment.delete()
    if comment_id in comment_ids:
        comment = Comment.objects.get(id=comment_id)
        OpenComment.objects.get_or_create(article=article, comment=comment, author=comment.author)
        article.closed = True
        article.save()
        print "successfully saved"
    else:
        print "the comment is not among the article's comments"

def delete_article(id):
    article = Article.objects.get(id = id)
    print id
    article.delete()


def add_close_comment(url, comment_id):
    article = Article.objects.get(url=url)
    comments = Comment.objects.filter(article_id = article.id)
    comment_ids = [c.id for c in comments]
    if comment_id in comment_ids:
        comment = Comment.objects.get(id=comment_id)
        CloseComment.objects.get_or_create(article=article, comment=comment, author=comment.author)
        article.closed = True
        article.save()
        print "successfully saved"
    else:
        print "the comment is not among the article's comments"

def get_final_closed_rfcs():
    close_comments = CloseComment.objects.all()
    for cc in close_comments:
        article_id = cc.article_id
        a = Article.objects.get(id = article_id)
        a.closed = True
        a.save()
# need to do with boundary because the first 2034 were done manually ###
def get_close_comment(boundary):
    # articles = Article.objects.all()
    # for article in articles:
    #     article_id = article.id
    #     try:
    #         open_comment = OpenComment.objects.get(article_id = article_id)
    #     except Exception:
    #         open_comment = None
    #
    #     article_comments = Comment.objects.filter(article_id = article_id)
    #     for comment in article_comments:
    #         if re.search(_CLOSE_COMMENT_RE, comment.text):
    #             # check if the comment is the same as the open comment
    #             if open_comment and comment.id != open_comment.comment_id:
    #                 CloseComment.objects.get_or_create(article = article, comment = comment, author = comment.author)
    #                 article.closed = True
    #                 print article.id
    #                 article.save()

    remaining_articles = Article.objects.filter(closed=False)
    for article in remaining_articles:
        article_id = article.id
        try:
            open_comment = OpenComment.objects.get(article_id=article_id)
        except Exception:
            open_comment = None
        article_comments = Comment.objects.filter(article_id=article_id)
        for comment in article_comments:
            if re.search(_CLOSE_COMMENT_RE, comment.text):
                # check if the comment is the same as the open comment
                if open_comment and comment.id == open_comment.comment_id:
                    # get the latest id
                    chosen_comment = Comment.objects.filter(article_id=article.id, created_at__isnull=False).order_by('-created_at').first()
                    CloseComment.objects.get_or_create(article=article, comment=chosen_comment, author=chosen_comment.author)
                    article.closed = True
                    print article.id
                    article.save()
                    break



def get_open_comment():
    articles = Article.objects.all()
    for article in articles:
        print article.id
        article_comments = Comment.objects.filter(article_id = article.id, created_at__isnull=False).exclude(author_id=13891).order_by('created_at')
        #get the most oldest one
        open_comment = article_comments.first()
        if open_comment:
            OpenComment.objects.get_or_create(article = article, comment = open_comment, author = open_comment.author)


def get_article(url, source, num):
    article = Article.objects.filter(url=url)
    if article.count() == 0:
        if source.source_name == "The Atlantic":
            
            url = url.strip().split('?')[0]
            
            thread_call = THREAD_CALL % (DISQUS_API_KEY, source.disqus_name, url)
            result = urllib2.urlopen(thread_call)
            result = json.load(result)
            
            if len(result['response']) > 1 and result['response'][0]['link'] != url:
                return None
            
            title = result['response'][0]['clean_title']
            link = result['response'][0]['link']
            id = result['response'][0]['id']
            
        elif source.source_name == "Reddit":
            r = praw.Reddit(user_agent=USER_AGENT)
            submission = r.get_submission(url)
            title = submission.title
            link = url
            id = submission.id
            
        elif source.source_name == "Wikipedia Talk Page":
            url_parts = url.split('/wiki/')
            domain = url_parts[0]
            wiki_sub = url_parts[1].split(':')
            wiki_parts = ':'.join(wiki_sub[1:]).split('#')
            wiki_page = wiki_parts[0]
            section = None
            if len(wiki_parts) > 1:
                section = wiki_parts[1]

            print domain
            from wikitools import wiki, api
            site = wiki.Wiki(domain + '/w/api.php')
            page = urllib2.unquote(str(wiki_sub[0]) + ':' + wiki_page.encode('ascii', 'ignore'))
            params = {'action': 'parse', 'prop': 'sections','page': page ,'redirects':'yes' }
            from wikitools import wiki, api
            try:
                request = api.APIRequest(site, params)

                result = request.query()

                id = str(result['parse']['pageid'])
                section_title = None
                section_index = None

                if section:
                    for s in result['parse']['sections']:
                        if s['anchor'] == section:
                            id = str(id) + '#' + str(s['index'])
                            section_title = s['line']
                            section_index = s['index']
                title = result['parse']['title']

                if section_title:
                    title = title + ' # ' + section_title

                link = urllib2.unquote(url)
                article,_ = Article.objects.get_or_create(disqus_id=id, title=title, url=link, source=source, section_index=section_index)

            except api.APIError:
                pass
    else:
        article = article[num]
        
    return article

def get_source(url):
    if 'theatlantic' in url:
        return Source.objects.get(source_name="The Atlantic")
    elif 'reddit.com' in url:
        return Source.objects.get(source_name="Reddit")
    elif 'wikipedia.org/wiki/' in url:
        return Source.objects.get(source_name="Wikipedia Talk Page")
    return None

def _correct_signature_before_parse(text):
    _user_re = "(\(?\[\[\W*user\W*:(.*?)\|[^\]]+\]\]\)?)"
    _user_talk_re = "(\(?\[\[\W*user[_ ]talk\W*:(.*?)\|[^\]]+\]\]\)?)"
    _user_contribs_re = "(\(?\[\[\W*Special:Contributions/(.*?)\|[^\]]+\]\]\)?)"

    # different format from the ones in signatureutils.py. need to divide (UTC) from time
    # 01:52, 20 September 2013
    _timestamp_re_0 = r"[0-9]{2}:[0-9]{2},? [0-9]{1,2} [^\W\d]+ [0-9]{4}"
    # 18:45 Mar 10, 2003
    _timestamp_re_1 = r"[0-9]{2}:[0-9]{2},? [^\W\d]+ [0-9]{1,2},? [0-9]{4}"
    # 01:54:53, 2005-09-08
    _timestamp_re_2 = r"[0-9]{2}:[0-9]{2}:[0-9]{2},? [0-9]{4}-[0-9]{2}-[0-9]{2}"
    _timestamps = [_timestamp_re_0, _timestamp_re_1, _timestamp_re_2]

    # case 1
    # example url: https://en.wikipedia.org/wiki/Talk:Race_and_genetics#RFC
    text = text.replace("(UTC\n", "(UTC)\n")

    # case 2: get rid of user name's italics
    # especially needed when the signature doesn't have timestamp: https://en.wikipedia.org/wiki/Wikipedia_talk:What_Wikipedia_is_not/Archive_49#RfC:_amendment_to_WP:NOTREPOSITORY
    italics_user_re = re.compile(r"'+<.*?>(?P<user>(" + '|'.join([_user_re, _user_talk_re, _user_contribs_re]) + "))<.*?>'+", re.I)
    text = re.sub(italics_user_re, '\g<user>', text)

    # case 3: when there are space(s) or new line(s) between user name and time or time and (UTC)
    wrong_sig_re = re.compile(
        r"((\n)*(?P<user>(" + '|'.join([_user_re, _user_talk_re, _user_contribs_re]) + "))( |\n|<.*?>)*"
                                                                                       "(?P<time>(" + r'|'.join(_timestamps) + "))( |\n)*(\(UTC\))?)", re.I)
    text = re.sub(wrong_sig_re, '\g<user> \g<time> (UTC)', text)

    # case 4
    text = text.replace("(UTC)}}", "(UTC)}}\n")
    return text

def _clean_wiki_text(text):
    # case 1: correct wrong signature formats
    text = _correct_signature_before_parse(text)

    # case 2 : when ":" and "*" are mixed together, such as in "\n:*::"
    # example: https://en.wikipedia.org/w/api.php?action=query&titles=Talk:God_the_Son&prop=revisions&rvprop=content&format=json
    mixed_indent_re = "(?P<before>\n:)\*(?P<after>:+)"
    text = re.sub(mixed_indent_re, "\g<before>\g<after>",text)

    # case 3
    start = re.compile('<(div|small).*?>', re.DOTALL)
    end = re.compile('</(div|small).*?>', re.DOTALL)
    template = re.compile('<!--.*?-->', re.DOTALL)
    for target in [start, end, template]:
        text = re.sub(target, '', text)

    # case 4: "&nbsp;" breaks parsing
    # example: <span style=\"border:1px solid #329691;background:#228B22;\">'''[[User:Viridiscalculus|<font color=\"#FFCD00\">&nbsp;V</font>]][[User talk:Viridiscalculus|<font style=\"color:#FFCD00\">C&nbsp;</font>]]'''</span> 01:25, 4 January 2012 (UTC)
    text = text.replace("&nbsp;", " ")

    # case 5
    unicode_re = re.compile('\\\\u[0-9a-z]{4}', re.UNICODE | re.IGNORECASE)
    text = re.sub(unicode_re, '', text)

    # case 6: Editors tend to put ':' infront of {{outdent}} for visualization but this breaks parsing properly.
    # example url : https://en.wikipedia.org/wiki/Talk:No%C3%ABl_Coward/Archive_2#RfC:_Should_an_Infobox_be_added_to_the_page.3F
    wrong_outdent_temp = re.compile(":+( )*{{(outdent|od|unindent).*?}}", re.I)
    text = re.sub(wrong_outdent_temp, "{{outdent}}\n", text)
    return text.strip()


def get_wiki_talk_posts(article, current_task, total_count):
    def get_section(sections, section_title):
        for s in sections:
            heading_title = s.get('heading', '')
            heading_title = re.sub(r'\]', '', heading_title)
            heading_title = re.sub(r'\[', '', heading_title)
            heading_title = re.sub('<[^<]+?>', '', heading_title)
            if heading_title.strip() == str(section_title).strip():
                return s

    def find_outer_section(title, text, id):
        # Check if closing comment is in here, if not look for the outer section.
        # If there is an outer section, choose it only if it has a closing statement,
        if len(title)>1:
            section_title = title[1].encode('ascii', 'ignore')
            params = {'action': 'query', 'titles': title[0], 'prop': 'revisions', 'rvprop': 'content', 'format': 'json', 'redirects': 'yes'}
            result = api.APIRequest(site, params).query()
            whole_text = _clean_wiki_text(result['query']['pages'][id]['revisions'][0]['*'])
            # whole_text = result['query']['pages'][id]['revisions'][0]['*']

            import wikichatter as wc
            parsed_whole_text = wc.parse(whole_text.encode('ascii','ignore'))
            sections = parsed_whole_text['sections']

            for outer_section in sections:
                found_subection = get_section(outer_section['subsections'], section_title)
                if found_subection:
                    outer_comments = outer_section['comments']
                    for comment in outer_comments:
                        comment_text = '\n'.join(comment['text_blocks'])
                        if re.search(_CLOSE_COMMENT_RE, comment_text):
                            params = {'action': 'parse', 'prop': 'sections', 'page': title[0], 'redirects': 'yes'}
                            result = api.APIRequest(site, params).query()
                            for s in result['parse']['sections']:
                                if s['line'] == outer_section.get('heading').strip():
                                    section_index = s['index']
                                    params = {'action': 'query', 'titles': title[0], 'prop': 'revisions',
                                               'rvprop': 'content', 'rvsection': section_index, 'format': 'json',
                                              'redirects': 'yes'}
                                    result = api.APIRequest(site, params).query()
                                    final_section_text = result['query']['pages'][id]['revisions'][0]['*']
                                    return final_section_text
        return text

    from wikitools import wiki, api
    domain = article.url.split('/wiki/')[0]
    site = wiki.Wiki(domain + '/w/api.php')
    
    title = article.title.split(' # ')
    print "retrieved title"
    print title
    # "section_index" is the index number of the section within the page.
    # There are some cases when wikicode does not parse a section as a section when given a "whole page".
    # To prevent this, we first grab only the section(not the entire page) using "section_index" and parse it.
    section_index = article.section_index

    params = {'action': 'query', 'titles': title[0],'prop': 'revisions', 'rvprop': 'content', 'format': 'json','redirects':'yes'}
    if section_index:
        params['rvsection'] = section_index
    request = api.APIRequest(site, params)
    result = request.query()
    id = article.disqus_id.split('#')[0]

    if id in result['query']['pages']:
        text = result['query']['pages'][id]['revisions'][0]['*']


    # If there isn't a closing statement, it means that the RfC could exist as a subsection of another section, with the closing statement in the parent section.
    # Example: https://en.wikipedia.org/wiki/Talk:Alexz_Johnson#Lead_image
        if not re.search(_CLOSE_COMMENT_RE, text):
            text = find_outer_section(title, text, id)

        text = _clean_wiki_text(text)

        import wikichatter as wc
        parsed_text = wc.parse(text.encode('ascii','ignore'))

        start_sections = parsed_text['sections']
        if len(title) > 1:
            section_title = title[1].encode('ascii','ignore')
            sections = parsed_text['sections']
            found_section = get_section(sections, section_title)
            if found_section:
                start_sections = found_section['subsections']
                start_comments = found_section['comments']
                total_count = import_wiki_talk_posts(start_comments, article, None, current_task, total_count)

        total_count = import_wiki_sessions(start_sections, article, None, current_task, total_count)

        #save the closing and open comment
        article_comments = Comment.objects.filter(article_id=article.id, created_at__isnull=False).exclude(author_id=13891).order_by('created_at')
        open_comment = article_comments.first() # get the most oldest one
        if open_comment:
            OpenComment.objects.get_or_create(article=article, comment=open_comment, author=open_comment.author)

        article_comments = Comment.objects.filter(article_id=article.id)
        for comment in article_comments:
            if re.search(_CLOSE_COMMENT_RE, comment.text):
                CloseComment.objects.get_or_create(article=article, comment=comment, author=comment.author)
                article.closed = True
                article.save()


def import_wiki_sessions(sections, article, reply_to, current_task, total_count):
    for section in sections:
        heading = section.get('heading', None)
#         if heading:
#             parsed_text = heading
#             comment_author = CommentAuthor.objects.get(disqus_id='anonymous', is_wikipedia=True)
#             
#             comments = Comment.objects.filter(article=article, author=comment_author, text=parsed_text)
#             if comments.count() > 0:
#                 comment_wikum = comments[0]
#             else:
#                 comment_wikum = Comment.objects.create(article = article,
#                                                        author = comment_author,
#                                                        text = parsed_text,
#                                                        reply_to_disqus = reply_to,
#                                                        text_len = len(parsed_text),
#                                                        )
#                 comment_wikum.save()
#                 comment_wikum.disqus_id = comment_wikum.id
#                 comment_wikum.save()
#                 
#             disqus_id = comment_wikum.disqus_id
#                 
#             total_count += 1
#             
#             if current_task and total_count % 3 == 0:
#                 current_task.update_state(state='PROGRESS',
#                                           meta={'count': total_count})
#             
#         else:
        disqus_id = reply_to
        
        if len(section['comments']) > 0:
            total_count = import_wiki_talk_posts(section['comments'], article, disqus_id, current_task, total_count)
        if len(section['subsections']) > 0:
            total_count = import_wiki_sessions(section['subsections'], article, disqus_id, current_task, total_count)
    return total_count
    
def import_wiki_authors(authors, article):
    found_authors = []
    anonymous_exist = False
    for author in authors:
        if author:
            found_authors.append(author)
        else:
            anonymous_exist = True
    authors_list = '|'.join(found_authors)
    
    from wikitools import wiki, api
    domain = article.url.split('/wiki/')[0]
    site = wiki.Wiki(domain + '/w/api.php')
    params = {'action': 'query', 'list': 'users', 'ususers': authors_list, 'usprop': 'blockinfo|groups|editcount|registration|emailable|gender', 'format': 'json'}

    request = api.APIRequest(site, params)
    result = request.query()
    comment_authors = []
    for user in result['query']['users']:
        try:
            author_id = user['userid']
            comment_author = CommentAuthor.objects.filter(disqus_id=author_id)
            if comment_author.count() > 0:
                comment_author = comment_author[0]
            else:
                joined_at = datetime.datetime.strptime(user['registration'], '%Y-%m-%dT%H:%M:%SZ')
                comment_author = CommentAuthor.objects.create(username=user['name'], 
                                                              disqus_id=author_id,
                                                              joined_at=user['registration'],
                                                              edit_count=user['editcount'],
                                                              gender=user['gender'],
                                                              groups=','.join(user['groups']),
                                                              is_wikipedia=True
                                                              )
        except Exception:
            comment_author = CommentAuthor.objects.create(username=user['name'], is_wikipedia=True)
        comment_authors.append(comment_author)

    if anonymous_exist:
        comment_authors.append(CommentAuthor.objects.get(disqus_id='anonymous', is_wikipedia=True))

    return comment_authors

def fix_null_co(comment_wikum):
    text = comment_wikum.text
    article = Article.objects.get(id=comment_wikum.article_id)

    import wikichatter as wc
    parsed_text = wc.parse(text.encode('ascii', 'ignore'))

    section = parsed_text['sections'][0]
    comments = section['comments']
    for comment in comments:
        author = comment.get('author')

        if author:
            try:
                comment_author = CommentAuthor.objects.get(username=author)
            except Exception:
                comment_author = import_wiki_authors([author], article)[0]


        else:
            comment_author = CommentAuthor.objects.get(disqus_id='anonymous', is_wikipedia=True)

        # cosigners = [sign['author'] for sign in comment['cosigners']]
        # comment_cosigners = import_wiki_authors(cosigners, article)
        # print comment_author
        comment_wikum.author = comment_author
        comment_wikum.save()


def fix_null_comments():
    null_comments = Comment.objects.filter(author_id=None)

    for comment_wikum in null_comments:
        text = comment_wikum.text
        article = Article.objects.get(id = comment_wikum.article_id)

        import wikichatter as wc
        parsed_text = wc.parse(text.encode('ascii','ignore'))

        section = parsed_text['sections'][0]
        comments = section['comments']
        for comment in comments:
            author = comment.get('author')

            if author:
                try:
                    comment_author = CommentAuthor.objects.get(username=author)
                except Exception:
                    comment_author = import_wiki_authors([author], article)[0]


            else:
                comment_author = CommentAuthor.objects.get(disqus_id='anonymous', is_wikipedia=True)

            # cosigners = [sign['author'] for sign in comment['cosigners']]
            # comment_cosigners = import_wiki_authors(cosigners, article)
            comment_wikum.author = comment_author
            comment_wikum.save()

            # for signer in comment_cosigners:
            #     comment_wikum.cosigners.add(signer)


def import_wiki_talk_posts(comments, article, reply_to, current_task, total_count):    
    for comment in comments:
        text = '\n'.join(comment['text_blocks'])
        author = comment.get('author')

        if author:
            comment_author = import_wiki_authors([author], article)[0]
        else:
            comment_author = CommentAuthor.objects.get(disqus_id='anonymous', is_wikipedia=True)
            
        comments = Comment.objects.filter(article=article, author=comment_author,text=text)
        if comments.count() > 0:
            comment_wikum = comments[0]
        else:
            # time = None
            timestamp = comment.get('time_stamp')
            # if timestamp:
            #     formats = ['%H:%M, %d %B %Y (%Z)', '%H:%M, %d %b %Y (%Z)', '%H:%M %b %d, %Y (%Z)']
            #     for date_format in formats:
            #         try:
            #             time = datetime.datetime.strptime(timestamp, date_format)
            #         except ValueError:
            #             pass
            cosigners = [sign['author'] for sign in comment['cosigners']]
            comment_cosigners = import_wiki_authors(cosigners, article)

            comment_wikum = Comment.objects.create(article = article,
                                                   author = comment_author,
                                                   text = text,
                                                   reply_to_disqus = reply_to,
                                                   text_len = len(text),
                                                   )
            # if time:
                # comment_wikum.created_at = time
            if timestamp:
                comment_wikum.created_at = timestamp

            comment_wikum.save()
            comment_wikum.disqus_id = comment_wikum.id
            comment_wikum.save()
            
            for signer in comment_cosigners:
                comment_wikum.cosigners.add(signer)
        
        total_count += 1
        
        if current_task and total_count % 3 == 0:
            current_task.update_state(state='PROGRESS',
                                      meta={'count': total_count})
        
        replies = comment['comments']
        total_count = import_wiki_talk_posts(replies, article, comment_wikum.disqus_id, current_task, total_count)
    
    return total_count
        

def get_reddit_posts(article, current_task, total_count):
    r = praw.Reddit(user_agent=USER_AGENT)
    submission = r.get_submission(submission_id=article.disqus_id)

    submission.replace_more_comments(limit=None, threshold=0)
    
    all_forest_comments = submission.comments
    
    import_reddit_posts(all_forest_comments, article, None, current_task, total_count)
    
def count_replies(article):
    comments = Comment.objects.filter(article=article)
    for c in comments:
        if c.disqus_id != '':
            replies = Comment.objects.filter(reply_to_disqus=c.disqus_id, article=article).count()
            c.num_replies = replies
            c.save()


def get_disqus_posts(article, current_task, total_count):
    comment_call = COMMENTS_CALL % (DISQUS_API_KEY, article.disqus_id)
            
    result = urllib2.urlopen(comment_call)
    result = json.load(result)
    
    count = import_disqus_posts(result, article)
    
    if current_task:
        total_count += count
                    
        if total_count % 3 == 0:
            current_task.update_state(state='PROGRESS',
                                      meta={'count': total_count})
    
    while result['cursor']['hasNext']:
        next = result['cursor']['next']
        comment_call_cursor = '%s&cursor=%s' % (comment_call, next)
        
        
        result = urllib2.urlopen(comment_call_cursor)
        result = json.load(result)
        
        count = import_disqus_posts(result, article)
        
        if current_task:
            total_count += count
            
            if total_count % 3 == 0:
                current_task.update_state(state='PROGRESS',
                                          meta={'count': total_count})


def import_reddit_posts(comments, article, reply_to, current_task, total_count):
    
    if current_task and total_count % 3 == 0:
        current_task.update_state(state='PROGRESS',
                                  meta={'count': total_count})
    
    for comment in comments:
        
        comment_id = comment.id
        comment_wikum = Comment.objects.filter(disqus_id=comment_id, article=article)
        
        if comment_wikum.count() == 0:
            
            from praw.errors import NotFound
            
            try:
                author_id = comment.author.id
                comment_author = CommentAuthor.objects.filter(disqus_id=author_id)
                if comment_author.count() > 0:
                    comment_author = comment_author[0]
                else:
                    comment_author = CommentAuthor.objects.create(username=comment.author.name, 
                                                              disqus_id=author_id,
                                                              joined_at=datetime.datetime.fromtimestamp(int(comment.author.created_utc)),
                                                              is_reddit=True,
                                                              is_mod=comment.author.is_mod,
                                                              is_gold=comment.author.is_gold,
                                                              comment_karma=comment.author.comment_karma,
                                                              link_karma=comment.author.link_karma
                                                              )
            except AttributeError:
                comment_author = CommentAuthor.objects.get(disqus_id='anonymous', is_wikipedia=False)
            except NotFound:
                comment_author = CommentAuthor.objects.get(disqus_id='anonymous', is_wikipedia=False)
            
            html_text = comment.body_html
            html_text = re.sub('<div class="md">', '', html_text)
            html_text = re.sub('</div>', '', html_text)
            
            total_count += 1
            
            comment_wikum = Comment.objects.create(article = article,
                                             author = comment_author,
                                             text = html_text,
                                             disqus_id = comment.id,
                                             reply_to_disqus = reply_to,
                                             text_len = len(html_text),
                                             likes = comment.ups,
                                             dislikes = comment.downs,
                                             reports = len(comment.user_reports),
                                             points = comment.score,
                                             controversial_score = comment.controversiality,
                                             created_at=datetime.datetime.fromtimestamp(int(comment.created_utc)),
                                             edited = comment.edited,
                                             flagged = len(comment.user_reports) > 0,
                                             deleted = comment.banned_by != None,
                                             approved = comment.approved_by != None,
                                             )
            replies = comment.replies
            total_count = import_reddit_posts(replies, article, comment.id, current_task, total_count)
    
    return total_count

def import_disqus_posts(result, article):
    count = 0
    for response in result['response']:
        comment_id = response['id']
        comment = Comment.objects.filter(disqus_id=comment_id, article=article)
        
        if comment.count() == 0:
            
            count += 1
            
            anonymous = response['author']['isAnonymous']
            if anonymous:
                comment_author = CommentAuthor.objects.get(disqus_id='anonymous')
            else:
                author_id = response['author']['id']
                
                comment_author = CommentAuthor.objects.filter(disqus_id=author_id)
                if comment_author.count() > 0:
                    comment_author = comment_author[0]
                else:
                    
                    comment_author,_ = CommentAuthor.objects.get_or_create(username = response['author']['username'],
                                                          real_name = response['author']['name'],
                                                          power_contrib = response['author']['isPowerContributor'],
                                                          anonymous = anonymous,
                                                          reputation = response['author']['reputation'],
                                                          joined_at = datetime.datetime.strptime(response['author']['joinedAt'], '%Y-%m-%dT%H:%M:%S'),
                                                          disqus_id = author_id,
                                                          avatar = response['author']['avatar']['small']['permalink'],
                                                          primary = response['author']['isPrimary']
                                                          )
            
            comment = Comment.objects.create(article = article,
                                             author = comment_author,
                                             text = response['message'],
                                             disqus_id = response['id'],
                                             reply_to_disqus = response['parent'],
                                             text_len = len(response['message']),
                                             likes = response['likes'],
                                             dislikes = response['dislikes'],
                                             reports = response['numReports'],
                                             points = response['points'],
                                             created_at = datetime.datetime.strptime(response['createdAt'], '%Y-%m-%dT%H:%M:%S'),
                                             edited = response['isEdited'],
                                             spam = response['isSpam'],
                                             highlighted = response['isHighlighted'],
                                             flagged = response['isFlagged'],
                                             deleted = response['isDeleted'],
                                             approved = response['isApproved']
                                             )
        
    return count