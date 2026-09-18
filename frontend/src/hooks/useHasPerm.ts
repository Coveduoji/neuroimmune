import { useAuthStore } from '../stores/auth.store';
import { hasPerm } from '../lib/perm';

export function useHasPerm(perm: string): boolean {
  const user = useAuthStore((s) => s.user);
  return hasPerm(user, perm);
}
