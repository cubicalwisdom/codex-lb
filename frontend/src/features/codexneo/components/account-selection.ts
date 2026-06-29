export function applyAccountSelectionRange({
  current,
  visible,
  accountKey,
  checked,
  rangeSelect,
  anchorKey,
}: {
  current: string[];
  visible: string[];
  accountKey: string;
  checked: boolean;
  rangeSelect: boolean;
  anchorKey: string | null;
}) {
  const fallbackAnchor = current.find((key) => visible.includes(key)) ?? null;
  const resolvedAnchor = anchorKey ?? fallbackAnchor;
  const currentIndex = visible.indexOf(accountKey);
  const anchorIndex = resolvedAnchor ? visible.indexOf(resolvedAnchor) : -1;
  const keysToUpdate =
    rangeSelect && currentIndex >= 0 && anchorIndex >= 0
      ? visible.slice(Math.min(currentIndex, anchorIndex), Math.max(currentIndex, anchorIndex) + 1)
      : [accountKey];
  const next = new Set(current);

  for (const key of keysToUpdate) {
    if (checked) {
      next.add(key);
    } else {
      next.delete(key);
    }
  }
  return visible.filter((key) => next.has(key));
}
