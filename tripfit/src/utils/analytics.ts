type EventProps = Record<string, string | number | boolean | undefined>;

export function track(event: string, props: EventProps = {}) {
  // Placeholder analytics. Replace with Segment/Amplitude/Firebase later.
  // Keeping console output for local verification.
  // eslint-disable-next-line no-console
  console.log(`[event] ${event}`, props);
}
