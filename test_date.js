const details = { scheduled_time: null };

if (details.scheduled_time) {
    const dateObj = new Date(details.scheduled_time);
    const offset = dateObj.getTimezoneOffset() * 60000;
    const localISOTime = new Date(dateObj.getTime() - offset).toISOString().slice(0, 16);
    console.log(localISOTime)
} else {
    // Default to 1 week from now natively in the UI
    const nextWeek = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
    const offset = nextWeek.getTimezoneOffset() * 60000;
    const localISOTime = new Date(nextWeek.getTime() - offset).toISOString().slice(0, 16);
    console.log("fallback: ", localISOTime)
}
