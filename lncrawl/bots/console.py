#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import os
import sys
import shutil
import logging
from PyInquirer import prompt

from ..core import display
from ..core.app import App
from ..assets.icons import Icons
from ..core.arguments import get_args
from ..spiders import crawler_list
from ..binders import available_formats
from ..utils.kindlegen_download import download_kindlegen, retrieve_kindlegen

logger = logging.getLogger('CONSOLE_INTERFACE')


class ConsoleBot:
    def start(self):
        self.app = App()
        self.app.initialize()

        self.app.user_input = self.get_novel_url()
        try:
            self.app.init_search()
        except:
            return display.url_not_recognized()
        # end if

        if not self.app.crawler:
            self.app.crawler_links = self.get_crawlers_to_search()
            self.app.search_novel()

            novel_url = self.choose_a_novel()
            logger.info('Selected novel: %s' % novel_url)
            self.app.init_crawler(novel_url)
        # end if

        if self.app.can_login:
            self.app.login_data = self.get_login_info()
        # end if

        self.app.get_novel_info()

        self.app.output_path = self.get_output_path()
        self.app.chapters = self.process_chapter_range()

        self.app.output_formats = self.get_output_formats()
        self.app.pack_by_volume = self.should_pack_by_volume()

        self.app.start_download()
        self.app.bind_books()

        # self.app.compress_output()
    # end def

    def process_chapter_range(self):
        chapters = []
        res = self.get_range_selection()

        args = get_args()
        if res == 'all':
            chapters = self.app.crawler.chapters[:]
        elif res == 'first':
            n = args.first or 10
            chapters = self.app.crawler.chapters[:n]
        elif res == 'last':
            n = args.last or 10
            chapters = self.app.crawler.chapters[-n:]
        elif res == 'page':
            start, stop = self.get_range_using_urls()
            chapters = self.app.crawler.chapters[start:(stop + 1)]
        elif res == 'range':
            start, stop = self.get_range_using_index()
            chapters = self.app.crawler.chapters[start:(stop + 1)]
        elif res == 'volumes':
            selected = self.get_range_from_volumes()
            chapters = [
                chap for chap in self.app.crawler.chapters
                if selected.count(chap['volume']) > 0
            ]
        elif res == 'chapters':
            selected = self.get_range_from_chapters()
            chapters = [
                chap for chap in self.app.crawler.chapters
                if selected.count(chap['id']) > 0
            ]
        # end if

        if len(chapters) == 0:
            raise Exception('No chapters to download')
        # end if

        logger.debug('Selected chapters:')
        logger.debug(chapters)
        logger.info('%d chapters to be downloaded', len(chapters))

        return chapters
    # end def

    def get_novel_url(self):
        '''Returns a novel page url or a query'''
        args = get_args()
        if args.query and len(args.query) > 1:
            return args.query
        # end if

        url = args.novel_page
        if url and url.startswith('http'):
            return url
        # end if

        try:
            if args.suppress:
                raise Exception()
            # end if

            answer = prompt([
                {
                    'type': 'input',
                    'name': 'novel',
                    'message': 'Enter novel page url or query novel:',
                    'validate': lambda val: 'Input should not be empty'
                    if len(val) == 0 else True,
                },
            ])
            return answer['novel'].strip()
        except:
            raise Exception('Novel page url or query was not given')
        # end try
    # end def

    def get_crawlers_to_search(self):
        '''Returns user choice to search the choosen sites for a novel'''
        links = self.app.crawler_links
        if not links:
            return None

        args = get_args()
        if args.suppress:
            return links
        # end if

        answer = prompt([
            {
                'type': 'checkbox',
                'name': 'sites',
                'message': 'Where to search?',
                'choices': [{'name': x} for x in links],
            }
        ])

        selected = answer['sites']
        return selected if len(selected) > 0 else links
    # end def

    def choose_a_novel(self):
        '''Choose a single novel url from the search result'''
        args = get_args()

        choices = self.app.search_results
        if len(choices) == 0:
            raise Exception('Lightnovel list is empty')
        elif len(choices) == 1:
            return choices[0][1]
        # end if

        if args.suppress:
            # Use the first result when input is suppressed
            return choices[0][1]
        # end if

        answer = prompt([
            {
                'type': 'list',
                'name': 'novel_url',
                'message': 'Which one is your novel?',
                'choices': [
                    {'name': '%s (%s)' % (x[0], x[1])}
                    for x in sorted(choices)
                ],
            }
        ])

        selected = answer['novel_url']
        selected = re.search('(https?://.*)', selected)
        url = selected.group(1).strip('()')
        return url
    # end def

    def get_login_info(self):
        '''Returns the (email, password) pair for login'''
        args = get_args()

        if args.login:
            return args.login
        # end if

        if args.suppress:
            return False
        # end if

        answer = prompt([
            {
                'type': 'confirm',
                'name': 'login',
                'message': 'Do you want to log in?',
                'default': False
            },
        ])

        if answer['login']:
            answer = prompt([
                {
                    'type': 'input',
                    'name': 'email',
                    'message': 'Email:',
                    'validate': lambda val: True if len(val)
                    else 'Email address should be not be empty'
                },
                {
                    'type': 'password',
                    'name': 'password',
                    'message': 'Password:',
                    'validate': lambda val: True if len(val)
                    else 'Password should be not be empty'
                },
            ])
            return answer['email'], answer['password']
        # end if

        return None
    # end if

    def get_output_path(self):
        '''Returns a valid output path where the files are stored'''
        args = get_args()
        output_path = args.output_path

        if args.suppress:
            if not output_path:
                output_path = self.app.output_path
            # end if
            if not output_path:
                output_path = os.path.join('Lightnovels', 'Unknown Novel')
            # end if
        # end if

        if not output_path:
            answer = prompt([
                {
                    'type': 'input',
                    'name': 'output',
                    'message': 'Enter output direcotry:',
                    'default': os.path.abspath(self.app.output_path),
                },
            ])
            output_path = answer['output']
        # end if

        output_path = os.path.abspath(output_path)
        if os.path.exists(output_path):
            if self.force_replace_old():
                shutil.rmtree(output_path, ignore_errors=True)
            # end if
        # end if
        os.makedirs(output_path, exist_ok=True)

        return output_path
    # end def

    def force_replace_old(self):
        args = get_args()

        if args.force:
            return True
        elif args.ignore:
            return False
        # end if

        if args.suppress:
            return False
        # end if

        answer = prompt([
            {
                'type': 'confirm',
                'name': 'force',
                'message': 'Detected existing folder. Replace it?',
                'default': False,
            },
        ])
        return answer['force']
    # end def

    def get_output_formats(self):
        '''Returns a dictionary of output formats.'''
        args = get_args()

        formats = args.output_formats
        # if not (formats or args.suppress):
        #     answer = prompt([
        #         {
        #             'type': 'checkbox',
        #             'name': 'formats',
        #             'message': 'Which output formats to create?',
        #             'choices': [{'name': x} for x in available_formats],
        #         },
        #     ])
        #     formats = answer['formats']
        # # end if

        if not formats or len(formats) == 0:
            formats = available_formats
        # end if

        return {x: (formats.count(x) > 0) for x in available_formats}
    # end def


    def should_pack_by_volume(self):
        '''Returns whether to generate single or multiple files by volumes'''
        args = get_args()

        if len(sys.argv) > 1:
            return args.byvol
        # end if

        if args.suppress:
            return False
        # end if

        answer = prompt([
            {
                'type': 'confirm',
                'name': 'volume',
                'message': 'Generate separate files for each volumes?',
                'default': False,
            },
        ])
        return answer['volume']
    # end def

    def get_range_selection(self):
        '''Returns a choice of how to select the range of chapters to downloads'''
        volume_count = len(self.app.crawler.volumes)
        chapter_count = len(self.app.crawler.chapters)
        selections = ['all', 'last', 'first', 'page', 'range', 'volumes', 'chapters']


        args = get_args()
        for key in selections:
            if args.__getattribute__(key):
                return key
            # end if
        # end if

        if args.suppress:
            return selections[0]
        # end if

        big_list_warn = '(warn: very big list)' if chapter_count > 50 else ''

        choices = [
            'Everything! (%d chapters)' % chapter_count,
            'Last 10 chapters',
            'First 10 chapters',
            'Custom range using URL',
            'Custom range using index',
            'Select specific volumes (%d volumes)' % volume_count,
            'Select specific chapters ' + big_list_warn,
        ]
        if chapter_count <= 20:
            choices.pop(1)
            choices.pop(1)
        # end if

        answer = prompt([
            {
                'type': 'list',
                'name': 'choice',
                'message': 'Which chapters to download?',
                'choices': choices,
            },
        ])

        return selections[choices.index(answer['choice'])]
    # end def

    def get_range_using_urls(self):
        '''Returns a range of chapters using start and end urls as input'''
        args = get_args()
        start_url, stop_url = args.page or (None, None)

        if args.suppress:
            return (0, len(self.app.crawler.chapters) - 1)
        # end if

        if not (start_url and stop_url):
            def validator(val):
                try:
                    if self.app.crawler.get_chapter_index_of(val) > 0:
                        return True
                except:
                    pass
                return 'No such chapter found given the url'
            # end def
            answer = prompt([
                {
                    'type': 'input',
                    'name': 'start_url',
                    'message': 'Enter start url:',
                    'validate': validator,
                },
                {
                    'type': 'input',
                    'name': 'stop_url',
                    'message': 'Enter final url:',
                    'validate': validator,
                },
            ])
            start_url = answer['start_url']
            stop_url = answer['stop_url']
        # end if

        start = self.app.crawler.get_chapter_index_of(start_url) - 1
        stop = self.app.crawler.get_chapter_index_of(stop_url) - 1

        return (start, stop) if start < stop else (stop, start)
    # end def

    def get_range_using_index(self):
        '''Returns a range selected using chapter indices'''
        chapter_count = len(self.app.crawler.chapters)

        args = get_args()
        start, stop = args.range or (None, None)

        if args.suppress:
            return (0, chapter_count - 1)
        # end if

        if not (start and stop):
            def validator(val):
                try:
                    if 1 <= int(val) <= chapter_count:
                        return True
                except:
                    pass
                return 'Please enter an integer between 1 and %d' % chapter_count
            # end def
            answer = prompt([
                {
                    'type': 'input',
                    'name': 'start',
                    'message': 'Enter start index (1 to %d):' % chapter_count,
                    'validate': validator,
                    'filter': lambda val: int(val),
                },
                {
                    'type': 'input',
                    'name': 'stop',
                    'message': 'Enter final index (1 to %d):' % chapter_count,
                    'validate': validator,
                    'filter': lambda val: int(val),
                },
            ])
            start = answer['start'] - 1
            stop = answer['stop'] - 1
        else:
            start = start - 1
            stop = stop - 1
        # end if

        return (start, stop) if start < stop else (stop, start)
    # end def

    def get_range_from_volumes(self, times=0):
        '''Returns a range created using volume list'''
        selected = None
        args = get_args()

        if args.suppress:
            selected = [x['id'] for x in self.app.crawler.volumes]
        # end if

        if times == 0 and not selected:
            selected = args.volumes
        # end if

        if not selected:
            answer = prompt([
                {
                    'type': 'checkbox',
                    'name': 'volumes',
                    'message': 'Choose volumes to download:',
                    'choices': [
                        {
                            'name': '%d - %s [%d chapters]' % (
                                vol['id'], vol['title'], vol['chapter_count'])
                        }
                        for vol in self.app.crawler.volumes
                    ],
                    'validate': lambda ans: True if len(ans) > 0
                    else 'You must choose at least one volume.'
                }
            ])
            selected = [
                int(val.split(' ')[0])
                for val in answer['volumes']
            ]
        # end if

        if times < 3 and len(selected) == 0:
            return self.get_range_from_volumes(times + 1)
        # end if

        return selected
    # end def

    def get_range_from_chapters(self, times=0):
        '''Returns a range created using individual chapters'''
        selected = None
        args = get_args()

        if args.suppress:
            selected = self.app.crawler.chapters
        # end if

        if times == 0 and not selected:
            selected = get_args().chapters
        # end if

        if not selected:
            answer = prompt([
                {
                    'type': 'checkbox',
                    'name': 'chapters',
                    'message': 'Choose chapters to download:',
                    'choices': [
                        {'name': '%d - %s' % (chap['id'], chap['title'])}
                        for chap in self.app.crawler.chapters
                    ],
                    'validate': lambda ans: True if len(ans) > 0
                    else 'You must choose at least one chapter.',
                }
            ])
            selected = [
                int(val.split(' ')[0])
                for val in answer['chapters']
            ]
        else:
            selected = [
                self.app.crawler.get_chapter_index_of(x)
                for x in selected if x
            ]
        # end if

        if times < 3 and len(selected) == 0:
            return self.get_range_from_chapters(times + 1)
        # end if

        selected = [
            x for x in selected
            if 1 <= x <= len(self.app.crawler.chapters)
        ]

        return selected
    # end def
# end class
