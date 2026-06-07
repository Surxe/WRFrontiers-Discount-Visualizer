const MONTHS_LONG = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const MONTH_LOOKUP = new Map([
  ...MONTHS_LONG.map((month, index) => [month.toLowerCase(), index + 1]),
  ...MONTHS_SHORT.map((month, index) => [month.toLowerCase(), index + 1]),
]);

function monthNumber(month) {
  if (Number.isInteger(month)) return month;
  if (typeof month === 'number') return Math.trunc(month);
  const key = String(month || '').trim().toLowerCase();
  return MONTH_LOOKUP.get(key) || MONTH_LOOKUP.get(key.slice(0, 3));
}

function parsePart(part, fallbackMonth, fallbackYear) {
  const cleaned = String(part || '').replace(/(\d+)(st|nd|rd|th)/gi, '$1').trim();
  const match = cleaned.match(/([A-Za-z]+)?\s*(\d{1,2})(?:,?\s*(\d{4}))?/);
  if (!match) return null;

  const [, monthText, dayText, yearText] = match;
  const month = monthText ? monthNumber(monthText) : fallbackMonth;
  const year = yearText ? Number(yearText) : fallbackYear;
  if (!month || !year) return null;

  return { year, month, day: Number(dayText) };
}

export function normalizeWeek(value) {
  if (!value) return null;

  const week = value.week || value;
  
  // Handle new format: month names without years (from Gemini CLI)
  const hasMonthNamesWithoutYears = [
    'start_month',
    'start_day',
    'end_month',
    'end_day',
  ].every((key) => week[key] !== undefined && week[key] !== null) &&
  week.start_year === undefined && week.end_year === undefined;

  if (hasMonthNamesWithoutYears) {
    const currentYear = new Date().getFullYear();
    const startMonth = monthNumber(week.start_month);
    const endMonth = monthNumber(week.end_month);
    
    // Compute years at runtime
    let startYear = currentYear;
    let endYear = currentYear;
    
    // Handle year rollover (e.g., December to January)
    if (endMonth < startMonth) {
      endYear = startYear + 1;
    }
    
    return {
      start_year: startYear,
      start_month: startMonth,
      start_day: Number(week.start_day),
      end_year: endYear,
      end_month: endMonth,
      end_day: Number(week.end_day),
    };
  }

  // Handle legacy format with years
  const hasStructuredFields = [
    'start_year',
    'start_month',
    'start_day',
    'end_year',
    'end_month',
    'end_day',
  ].every((key) => week[key] !== undefined && week[key] !== null);

  if (hasStructuredFields) {
    return {
      start_year: Number(week.start_year),
      start_month: monthNumber(week.start_month),
      start_day: Number(week.start_day),
      end_year: Number(week.end_year),
      end_month: monthNumber(week.end_month),
      end_day: Number(week.end_day),
    };
  }

  const dateRange = value.date_range || value.dateRange;
  if (!dateRange) return null;

  const parts = String(dateRange).trim().split(/\s+[-–—]\s+/);
  if (parts.length !== 2) return null;

  const currentYear = new Date().getFullYear();
  const start = parsePart(parts[0], null, currentYear);
  if (!start) return null;

  const end = parsePart(parts[1], start.month, start.year);
  if (!end) return null;

  if (start.month === 12 && end.month === 1 && !/\b\d{4}\b/.test(parts[1])) {
    end.year = start.year + 1;
  } else {
    const startDate = new Date(start.year, start.month - 1, start.day);
    const endDate = new Date(end.year, end.month - 1, end.day);
    if (endDate < startDate) end.year += 1;
  }

  return {
    start_year: start.year,
    start_month: start.month,
    start_day: start.day,
    end_year: end.year,
    end_month: end.month,
    end_day: end.day,
  };
}

export function weekStartDate(week) {
  const normalized = normalizeWeek(week);
  if (!normalized) return null;
  return new Date(normalized.start_year, normalized.start_month - 1, normalized.start_day);
}

export function weekEndDate(week) {
  const normalized = normalizeWeek(week);
  if (!normalized) return null;
  return new Date(normalized.end_year, normalized.end_month - 1, normalized.end_day, 23, 59, 59);
}

export function formatWeek(week, style = 'long') {
  const normalized = normalizeWeek(week);
  if (!normalized) return '';

  const monthNames = style === 'short' ? MONTHS_SHORT : MONTHS_LONG;
  const startMonth = monthNames[normalized.start_month - 1];
  const endMonth = monthNames[normalized.end_month - 1];

  const start = `${startMonth} ${normalized.start_day}`;
  const end = normalized.start_month === normalized.end_month
    ? String(normalized.end_day)
    : `${endMonth} ${normalized.end_day}`;

  if (style === 'short') return `${start} - ${end}`;

  if (normalized.start_year === normalized.end_year) {
    return `${start} - ${end} (${normalized.start_year})`;
  }

  return `${start} ${normalized.start_year} - ${endMonth} ${normalized.end_day} ${normalized.end_year}`;
}

export function weekYear(week) {
  const normalized = normalizeWeek(week);
  return normalized ? String(normalized.start_year) : String(new Date().getFullYear());
}
