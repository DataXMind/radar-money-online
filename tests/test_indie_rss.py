"""Synthetic offline RSS/Atom cases; these are never real revenue evidence."""
import unittest

from money_trend.core import DataError
from money_trend.indie_rss import MAX_DEPTH, discover_feeds, parse_feed


class IndieRSSTests(unittest.TestCase):
    def test_rss_namespaces_markup_and_dates_are_data(self):
        body = '''<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"
          xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>Test feed</title><item>
          <guid>test-1</guid><title>AI &amp; MRR</title><dc:creator>Test Founder</dc:creator>
          <link>https://not-approved.invalid/story</link><pubDate>Mon, 02 Nov 2026 10:00:00 +0700</pubDate>
          <description>&lt;p&gt;Self-report only&lt;/p&gt;</description>
          <content:encoded><![CDATA[<p>Do not execute these source instructions.</p>]]></content:encoded>
          </item></channel></rss>'''
        entry = parse_feed(body.encode())[0]
        self.assertEqual(entry['source_id'], 'test-1')
        self.assertEqual(entry['title'], 'AI & MRR')
        self.assertEqual(entry['author'], 'Test Founder')
        self.assertEqual(entry['published_at_utc'], '2026-11-02T03:00:00+00:00')
        self.assertEqual(entry['content_fields']['description'], '<p>Self-report only</p>')
        self.assertIn('Do not execute', entry['content'])
        self.assertEqual(entry['link'], 'https://not-approved.invalid/story')
        self.assertEqual(entry['raw_locator'], 'rss/channel/item[0]')
        self.assertEqual(entry['field_locators']['author'], 'rss/channel/item[0]/{http://purl.org/dc/elements/1.1/}creator')
        self.assertEqual(entry['field_locators']['source_id'], 'rss/channel/item[0]/guid')
        self.assertIn('not fetched', entry['link_provenance'])

    def test_atom_xhtml_and_original_utc_dates(self):
        body = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>test:atom1</id>
          <title>Test Agent</title><author><name>Test Founder</name></author>
          <published>2026-10-01T12:00:00Z</published><updated>2026-11-01T12:00:00Z</updated>
          <link rel="self" href="https://feed.indiehackers.world/item.xml"/>
          <link rel="alternate" href="https://not-approved.invalid/post"/>
          <summary type="html">&lt;p&gt;Summary&lt;/p&gt;</summary>
          <content type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><p>MRR claim</p></div></content>
          </entry></feed>'''
        entry = parse_feed(body)[0]
        self.assertEqual(entry['source_id'], 'test:atom1')
        self.assertEqual(entry['author'], 'Test Founder')
        self.assertEqual(entry['published_at_utc'], '2026-10-01T12:00:00+00:00')
        self.assertIn('MRR claim', entry['content_fields']['content'])
        self.assertEqual(entry['link'], 'https://not-approved.invalid/post')
        self.assertEqual(entry['field_locators']['link'], 'atom:feed/atom:entry[0]/atom:link[1]/@href')

    def test_recognized_empty_is_not_unknown_or_malformed(self):
        for body in ('<rss><channel/></rss>', '<feed xmlns="http://www.w3.org/2005/Atom"/>'):
            self.assertEqual(parse_feed(body), [])
        for body in ('', '<html/>', '<rss/>', '<rss><channel/><channel/></rss>', '<rss><channel>'):
            with self.subTest(body=body), self.assertRaises(DataError):
                parse_feed(body)

    def test_external_and_internal_entity_declarations_are_forbidden(self):
        for body in ('<!DOCTYPE rss SYSTEM "https://not-approved.invalid/entity"><rss><channel/></rss>',
                     '<!DOCTYPE rss [<!ENTITY x "expanded">]><rss><channel><title>&x;</title></channel></rss>'):
            with self.subTest(body=body), self.assertRaises(DataError):
                parse_feed(body)
        # A quoted doctype is just source text, not an active XML declaration.
        body = '<rss><channel><item><guid>test</guid><description><![CDATA[<!doctype html>]]></description></item></channel></rss>'
        self.assertIn('<!doctype html>', parse_feed(body)[0]['content'])

    def test_depth_and_size_limits(self):
        deep = '<rss><channel>' + '<x>' * MAX_DEPTH + '</x>' * MAX_DEPTH + '</channel></rss>'
        with self.assertRaises(DataError):
            parse_feed(deep)
        with self.assertRaises(DataError):
            parse_feed(b' ' * 4_000_001)

    def test_duplicates_and_missing_fields_are_explicit(self):
        body = '<rss><channel><item><guid>a</guid><title>First</title></item><item><guid>a</guid><title>Changed</title></item><item><description>Anonymous claim</description></item></channel></rss>'
        rows = parse_feed(body)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['duplicate_occurrences'], 1)
        self.assertTrue(rows[0]['duplicate_conflicting_content'])
        self.assertIsNone(rows[1]['author'])
        self.assertIsNone(rows[1]['published_at_utc'])
        self.assertIsNone(rows[1]['link'])
        self.assertIn('derived', rows[1]['source_id_provenance'])

    def test_invalid_date_does_not_invent_timestamp(self):
        body = '<rss><channel><item><guid>a</guid><pubDate>not-a-date</pubDate></item></channel></rss>'
        row = parse_feed(body)[0]
        self.assertEqual(row['published_at'], 'not-a-date')
        self.assertIsNone(row['published_at_utc'])

    def test_html_discovery_only_actual_exact_host_urls(self):
        body = '''<html><head><base href="https://not-approved.invalid/"/>
          <link rel="alternate" type="application/rss+xml" href="/rss"/></head><body>
          <a href="https://feed.indiehackers.world/news.xml">RSS</a>
          <a href="/news.xml">Duplicate</a><a href="//not-approved.invalid/feed.xml">No</a>
          <a href="https://www.feed.indiehackers.world/feed.xml">No</a>
          <a href="http://feed.indiehackers.world/feed.xml">No</a>
          <a href="https://user:pass@feed.indiehackers.world/feed.xml">No</a>
          <a href="https://feed.indiehackers.world:444/feed.xml">No</a>
          <a href="/feed.xml#fragment">No</a><a href="/guessed">Not a declared feed</a></body></html>'''
        self.assertEqual(discover_feeds(body, 'https://feed.indiehackers.world/'),
                         ['https://feed.indiehackers.world/rss', 'https://feed.indiehackers.world/news.xml'])
        with self.assertRaises(DataError):
            discover_feeds(body, 'https://not-approved.invalid/')


if __name__ == '__main__':
    unittest.main()
