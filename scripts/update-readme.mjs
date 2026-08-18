#!/usr/bin/env node
/**
 * scripts/update-readme.mjs
 *
 * Regenerates the dynamic sections of README.md:
 *   - fetchQuote()         -> <!--STARTS_HERE_QUOTE_README--> ... <!--ENDS_HERE_QUOTE_README-->
 *   - fetchGithubActivity() -> <!--START_SECTION:activity--> ... <!--END_SECTION:activity-->
 *   - fetchBlogFeed()      -> <!--START_SECTION:blog--> ... <!--END_SECTION:blog-->
 *
 * Zero external deps (uses Node 20's built-in fetch). Run via GitHub Actions
 * on a schedule, or locally with: node scripts/update-readme.mjs
 *
 * Env vars:
 *   GITHUB_USERNAME  - defaults to "Eliasilyz"
 *   BLOG_RSS_URL     - optional RSS/Atom feed URL; blog section is skipped if unset
 */

import { readFileSync, writeFileSync } from 'node:fs';

const README_PATH = 'README.md';
const GITHUB_USERNAME = process.env.GITHUB_USERNAME || 'Eliasilyz';
const BLOG_RSS_URL = process.env.BLOG_RSS_URL || '';

function readReadme() {
  return readFileSync(README_PATH, 'utf-8');
}

function writeReadme(content) {
  writeFileSync(README_PATH, content, 'utf-8');
}

function replaceBetweenMarkers(content, startMarker, endMarker, replacement) {
  const start = content.indexOf(startMarker);
  const end = content.indexOf(endMarker);
  if (start === -1 || end === -1 || end < start) {
    console.warn(`[update-readme] markers not found: ${startMarker} / ${endMarker}`);
    return content;
  }
  const before = content.slice(0, start + startMarker.length);
  const after = content.slice(end);
  return `${before}\n${replacement}\n${after}`;
}

async function fetchQuote() {
  try {
    const res = await fetch('https://programming-quotesapi.vercel.app/api/random');
    if (!res.ok) throw new Error(`status ${res.status}`);
    const data = await res.json();
    return `<i>\u275d"${data.quote}" \u2014 ${data.author}\u275e</i>`;
  } catch (err) {
    console.warn('[update-readme] fetchQuote failed:', err.message);
    return null;
  }
}

function formatEvent(ev) {
  const repo = ev.repo?.name;
  switch (ev.type) {
    case 'PushEvent':
      return `\ud83d\udd28 Pushed ${ev.payload.commits?.length ?? 0} commit(s) to [${repo}](https://github.com/${repo})`;
    case 'PullRequestEvent':
      return `\ud83d\udd00 ${ev.payload.action} a PR in [${repo}](https://github.com/${repo})`;
    case 'IssuesEvent':
      return `\ud83d\udccc ${ev.payload.action} an issue in [${repo}](https://github.com/${repo})`;
    case 'CreateEvent':
      return `\u2728 Created ${ev.payload.ref_type} in [${repo}](https://github.com/${repo})`;
    case 'WatchEvent':
      return `\u2b50 Starred [${repo}](https://github.com/${repo})`;
    default:
      return null;
  }
}

async function fetchGithubActivity(username, limit = 5) {
  try {
    const headers = { 'User-Agent': 'readme-bot', Accept: 'application/vnd.github+json' };
    if (process.env.GH_TOKEN) headers.Authorization = `Bearer ${process.env.GH_TOKEN}`;
    const res = await fetch(`https://api.github.com/users/${username}/events/public`, { headers });
    if (!res.ok) throw new Error(`status ${res.status}`);
    const events = await res.json();
    const lines = [];
    for (const ev of events) {
      if (lines.length >= limit) break;
      const line = formatEvent(ev);
      if (line) lines.push(`- ${line}`);
    }
    return lines.length ? lines.join('\n') : '_No recent public activity._';
  } catch (err) {
    console.warn('[update-readme] fetchGithubActivity failed:', err.message);
    return null;
  }
}

async function fetchBlogFeed(rssUrl, limit = 3) {
  if (!rssUrl) return null;
  try {
    const res = await fetch(rssUrl);
    if (!res.ok) throw new Error(`status ${res.status}`);
    const xml = await res.text();
    const items = [...xml.matchAll(/<item>([\s\S]*?)<\/item>/g)].slice(0, limit);
    const lines = items.map((m) => {
      const block = m[1];
      const title = block.match(/<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?<\/title>/)?.[1] ?? 'Untitled';
      const link = block.match(/<link>(.*?)<\/link>/)?.[1] ?? '#';
      return `- [${title}](${link})`;
    });
    return lines.length ? lines.join('\n') : null;
  } catch (err) {
    console.warn('[update-readme] fetchBlogFeed failed:', err.message);
    return null;
  }
}

async function main() {
  let content = readReadme();

  const quote = await fetchQuote();
  if (quote) {
    content = replaceBetweenMarkers(
      content,
      '<!--STARTS_HERE_QUOTE_README-->',
      '<!--ENDS_HERE_QUOTE_README-->',
      quote
    );
  }

  const activity = await fetchGithubActivity(GITHUB_USERNAME);
  if (activity) {
    content = replaceBetweenMarkers(
      content,
      '<!--START_SECTION:activity-->',
      '<!--END_SECTION:activity-->',
      activity
    );
  }

  const blog = await fetchBlogFeed(BLOG_RSS_URL);
  if (blog) {
    content = replaceBetweenMarkers(
      content,
      '<!--START_SECTION:blog-->',
      '<!--END_SECTION:blog-->',
      blog
    );
  }

  writeReadme(content);
  console.log('[update-readme] README.md updated.');
}

main().catch((err) => {
  console.error('[update-readme] fatal:', err);
  process.exit(1);
});
