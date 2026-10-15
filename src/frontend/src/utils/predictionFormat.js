// Display formatting for a prediction entry (one robot/titan in
// predictions.json). Shared by the /predictions cards, its og:image card, and
// its "Copy to share" text so every surface shows the same numbers.

/** Round to one decimal place; null passes through. */
export function round1(v) {
	return v == null ? null : Math.round(v * 10) / 10;
}

/** likelihood_pct (stored 0-100) as "51%" / "31.4%", or null when absent. */
export function formatLikelihood(bot) {
	const v = round1(bot?.likelihood_pct);
	return v == null ? null : `${v}%`;
}

/** True for a never-discounted (newly released) bot, which waits from its release. */
export function isNeverDiscounted(bot) {
	return bot?.weeks_since_discount == null && bot?.weeks_since_release != null;
}

/**
 * Wait summary for a bot.
 * long:  "13 wks since last discount · avg 9.8 wks"
 * short: "13 wks since · avg 9.8"
 */
export function formatWait(bot, { short = false } = {}) {
	if (isNeverDiscounted(bot)) {
		return short
			? `${bot.weeks_since_release} wks since release`
			: `${bot.weeks_since_release} wks since release · never discounted`;
	}
	if (bot?.weeks_since_discount == null) return '';
	if (short) {
		const avg = bot.avg_interval == null ? '' : ` · avg ${bot.avg_interval}`;
		return `${bot.weeks_since_discount} wks since${avg}`;
	}
	const avg = bot.avg_interval == null ? 'not enough history' : `avg ${bot.avg_interval} wks`;
	return `${bot.weeks_since_discount} wks since last discount · ${avg}`;
}
