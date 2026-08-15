export type View = 'triage' | 'hippocampus' | 'dashboard' | 'settings' | 'thalamus' | 'immune' | 'users';
export type NavTarget = { view?: View; caseId?: number };

let listener: ((t: NavTarget) => void) | null = null;

export function navigate(t: NavTarget): void {
  listener?.(t);
}

export function setNavListener(fn: ((t: NavTarget) => void) | null): void {
  listener = fn;
}
