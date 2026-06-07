import { normalizeWeek, weekEndDate, weekStartDate } from './weekDates.js';

export function parseDateRange(weekOrDateRange) {
  if (!weekOrDateRange) return null;
  const week = typeof weekOrDateRange === 'string'
    ? { date_range: weekOrDateRange }
    : weekOrDateRange;
  const normalized = normalizeWeek(week);
  if (!normalized) return null;

  return {
    start: weekStartDate(normalized),
    end: weekEndDate(normalized),
  };
}

export function getWeekStatus(weekOrDateRange) {
  const range = parseDateRange(weekOrDateRange);
  if (!range) return null;

  const now = new Date();
  if (now >= range.start && now <= range.end) return 'current';
  if (now < range.start) return 'upcoming';
  return 'past';
}

export function getCurrentOrLatestWeek(weeks) {
  if (!weeks || weeks.length === 0) return null;

  const now = new Date();
  for (const week of weeks) {
    const range = parseDateRange(week);
    if (range && now >= range.start && now <= range.end) {
      return week;
    }
  }

  return weeks[0];
}

function sortedWeeks(weeks) {
  return (weeks || [])
    .map((week) => ({ week, range: parseDateRange(week) }))
    .filter((entry) => entry.range)
    .sort((a, b) => a.range.start.getTime() - b.range.start.getTime());
}

/** Chronologically later week after the one being viewed (by slug or current week). */
export function getNextWeek(weeks, viewedSlug) {
  const sorted = sortedWeeks(weeks);
  if (sorted.length < 2) return null;

  let viewedIndex = -1;
  if (viewedSlug) {
    viewedIndex = sorted.findIndex((entry) => entry.week.slug === viewedSlug);
  } else {
    const active = getCurrentOrLatestWeek(weeks);
    if (active) viewedIndex = sorted.findIndex((entry) => entry.week.slug === active.slug);
  }

  if (viewedIndex === -1) return null;
  return sorted[viewedIndex + 1]?.week || null;
}

/** Chronologically earlier week before the one being viewed (by slug or current week). */
export function getPreviousWeek(weeks, viewedSlug) {
  const sorted = sortedWeeks(weeks);
  if (sorted.length < 2) return null;

  let viewedIndex = -1;
  if (viewedSlug) {
    viewedIndex = sorted.findIndex((entry) => entry.week.slug === viewedSlug);
  } else {
    const active = getCurrentOrLatestWeek(weeks);
    if (active) viewedIndex = sorted.findIndex((entry) => entry.week.slug === active.slug);
  }

  if (viewedIndex === -1) return null;
  return sorted[viewedIndex - 1]?.week || null;
}
