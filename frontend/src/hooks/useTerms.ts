import { useUiStore } from '../stores/ui.store';
import { TERM_DICT } from '../lib/terms';

export function useTerms() {
  const termMode = useUiStore((s) => s.termMode);
  const t = (key: string) => TERM_DICT[key]?.[termMode] ?? key;
  return { termMode, t };
}
