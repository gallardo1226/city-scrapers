# -*- coding: utf-8 -*-
"""
All spiders should yield data shaped according to the Open Civic Data
specification (http://docs.opencivicdata.org/en/latest/data/event.html).
"""
import re
import requests
import json
import scrapy
from datetime import datetime, timedelta

from city_scrapers.spider import Spider


class Chi_librarySpider(Spider):
    name = 'chi_library'
    long_name = 'Chicago Public Library'
    allowed_domains = ['https://www.chipublib.org/']
    start_urls = ['https://www.chipublib.org/board-of-directors/board-meeting-schedule/']

    def __init__(self, session=requests.Session()):
        """
        Initialize a spider with a session object to use in the
        _get_lib_info function.
        """
        self.session = session

    def parse(self, response):
        """
        `parse` should always `yield` a dict that follows the `Open Civic Data
        event standard <http://docs.opencivicdata.org/en/latest/data/event.html>`_.

        Change the `_parse_id`, `_parse_name`, etc methods to fit your scraping
        needs.
        """
        # the following code turns the HTML glob into an array of lists of strings, one list
        # per event. The first line is *always* the date, the last line is *always* the address.
        # IF the event has 3 lines, then line 2 and 3 should be concatenated to be the location.
        #Otherwise, the event has 3 lines and the middle line is the location.
        def cleanhtml(raw_html):
            cleanr = re.compile('<.*?>')
            cleantext = re.sub(cleanr, '', raw_html)
            return cleantext

        events = response.css('div.entry-content p').extract()
        year = response.css('div.entry-content h2').extract()

        all_clean_events = []
        for val in events:
            clean_event = cleanhtml(val)
            final_event = clean_event.splitlines()
            all_clean_events.append(final_event)

        # grab general information for event description
        description_str = ' '.join(all_clean_events[0] + all_clean_events[1])
        # remove first two informational lines from events array
        events_only = all_clean_events[2:]
        # get library info from City of Chicago API
        lib_info = self._get_lib_info()

        for item in events_only:
            date = item[0]
            date = re.sub(r'(,|\.)', '', date) + ' ' + cleanhtml(year[0])
            dt_obj = datetime.strptime(date, '%A %B %d %I %p %Y')

            data = {
                '_type': 'event',
                'name': 'Chicago Public Library Board Meeting',
                'description': description_str,
                'classification': 'Board meeting',
                'all_day': False,  # default is false
                'timezone': 'America/Chicago',
                'status': self._parse_status(item),  # default is tentative, but there is no status info on site
                'location': self._parse_location(item, lib_info),
                'sources': self._parse_sources(response),
                'documents': self._parse_documents(dt_obj)
            }
            data['id'] = self._generate_id(data)
            data.update(self._parse_datetimes(dt_obj))
            yield data

    def _get_lib_info(self):
        """
        Returns a list of dictionaries of information about each library
        from the City of Chicago's API.
        """
        r = self.session.get("https://data.cityofchicago.org/resource/psqp-6rmg.json")
        return json.loads(r.text)

    def _parse_classification(self, item):
        """
        Parse or generate classification (e.g. town hall).
        """
        return 'Not classified'

    def _parse_status(self, item):
        """
        Parse or generate status of meeting. Can be one of:

        * cancelled
        * tentative
        * confirmed
        * passed

        @TODO determine correct status
        """
        return 'tentative'

    def find_name(self, li):
        if len(li) == 4:
            return ', '.join(li[1:3])
        else:
            return li[1]

    def _parse_location(self, item, lib_info):
        """
        Parse or generate location. Url, latitutde and longitude are all
        optional and may be more trouble than they're worth to collect.
        """
        return {
            'url': None,
            'name': self.find_name(item),
            'coordinates': {
                'latitude': None,
                'longitude': None,
            },
            'address': self._parse_address(item, lib_info)
        }

    def _parse_address(self, item, lib_info):
        """
        compare item's address line to library API addresses until you find the match,
        then concatenate address line with city/state/zip to return address and maybe url?
        """
        if len(item) == 4:
            addr = 3
        else:
            addr = 2

        for i in range(len(lib_info)):
            if item[addr] == lib_info[i]['address']:
                match = lib_info[i]
                return match['address'] + ', ' + match['city'] + ' ' + match['state'] + ' ' + match['zip']

    def _parse_datetimes(self, dt_obj):
        """
        Parse start date and time.
        """
        # TODO: turn every event array's first string into correct date format
        date = dt_obj.date()
        return {
            'start': {
                'date': date,
                'time': dt_obj.time(),
                'note': ''
            },
            'end': {
                'date': date,
                'time': (dt_obj + timedelta(hours=3)).time(),
                'note': 'End time is estimated to be 3 hours after the start time'
            }
        }

    def _parse_documents(self, dt_obj):
        """
        Go to the page for the meeting and scrape the agenda, notes, etc from that page
        """
        url = 'https://www.chipublib.org/news/board-of-directors-meeting-agenda-' + dt_obj.strftime('%B-%d-%Y')
        yield scrapy.Request(url, callback=self._parse_document_page, dont_filter=True)

    def _parse_document_page(self, response):
        import pdb; pdb.set_trace()
        return []

    def _parse_sources(self, response):
        """
        Parse sources.
        """
        return [{'url': response.url, 'note': ''}]
