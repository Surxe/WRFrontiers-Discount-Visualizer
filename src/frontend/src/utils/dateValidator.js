export function parseDateRange(dateRangeStr) {
  if (!dateRangeStr) return null;
  
  const currentYear = new Date().getFullYear();
  const cleaned = dateRangeStr.replace(/\s+/g, ' ').trim();
  
  // Find all 4-digit years
  const yearMatches = cleaned.match(/\b(\d{4})\b/g);
  let startYear = currentYear;
  let endYear = currentYear;
  
  if (yearMatches) {
    if (yearMatches.length === 1) {
      startYear = parseInt(yearMatches[0], 10);
      endYear = startYear;
    } else {
      startYear = parseInt(yearMatches[0], 10);
      endYear = parseInt(yearMatches[yearMatches.length - 1], 10);
    }
  }
  
  const withoutYear = cleaned.replace(/,?\s*\b\d{4}\b/g, '');
  const parts = withoutYear.split('-');
  if (parts.length !== 2) return null;
  
  const startStr = parts[0].trim();
  const endStr = parts[1].trim();
  
  const startMatch = startStr.match(/([A-Za-z]+)\s+(\d+)/);
  if (!startMatch) return null;
  const startMonthStr = startMatch[1];
  const startDay = parseInt(startMatch[2], 10);
  
  let endMonthStr = startMonthStr;
  let endDay = null;
  
  const endMatch = endStr.match(/([A-Za-z]+)\s+(\d+)/);
  if (endMatch) {
    endMonthStr = endMatch[1];
    endDay = parseInt(endMatch[2], 10);
  } else {
    const endDayMatch = endStr.match(/(\d+)/);
    if (endDayMatch) {
      endDay = parseInt(endDayMatch[1], 10);
    }
  }
  
  if (endDay === null) return null;
  
  const monthMap = {
    jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5, jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11
  };
  
  const getMonthIndex = (mStr) => {
    const key = mStr.toLowerCase().substring(0, 3);
    return monthMap[key] !== undefined ? monthMap[key] : 0;
  };
  
  const startMonth = getMonthIndex(startMonthStr);
  const endMonth = getMonthIndex(endMonthStr);
  
  const startDate = new Date(startYear, startMonth, startDay, 0, 0, 0);
  let endDate = new Date(endYear, endMonth, endDay, 23, 59, 59);
  
  if (endDate < startDate) {
    if (!yearMatches || yearMatches.length < 2) {
      endDate = new Date(endYear + 1, endMonth, endDay, 23, 59, 59);
    }
  }
  
  return { start: startDate, end: endDate };
}

export function getWeekStatus(dateRangeStr) {
  const range = parseDateRange(dateRangeStr);
  if (!range) return null;
  
  const now = new Date();
  if (now >= range.start && now <= range.end) {
    return 'current';
  } else if (now < range.start) {
    return 'upcoming';
  } else {
    return 'past';
  }
}

export function getCurrentOrLatestWeek(weeks) {
  if (!weeks || weeks.length === 0) return null;
  
  const now = new Date();
  for (const week of weeks) {
    const range = parseDateRange(week.date_range);
    if (range && now >= range.start && now <= range.end) {
      return week;
    }
  }
  
  return weeks[0];
}

/** Chronologically later week after the one being viewed (by slug or current week). */
export function getNextWeek(weeks, viewedSlug) {
  if (!weeks?.length) return null;

  const sorted = weeks
    .map((week) => ({ week, range: parseDateRange(week.date_range) }))
    .filter((entry) => entry.range)
    .sort((a, b) => a.range.start.getTime() - b.range.start.getTime());

  if (sorted.length < 2) return null;

  let viewedIndex = -1;
  if (viewedSlug) {
    viewedIndex = sorted.findIndex((entry) => entry.week.slug === viewedSlug);
  } else {
    const active = getCurrentOrLatestWeek(weeks);
    if (active) {
      viewedIndex = sorted.findIndex((entry) => entry.week.slug === active.slug);
    }
  }

  if (viewedIndex === -1) return null;

  const next = sorted[viewedIndex + 1];
  return next ? next.week : null;
}
