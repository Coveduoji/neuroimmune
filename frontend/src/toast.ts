type Listener = (msg: string) => void;
let listener: Listener | null = null;

export function toast(msg: string): void {
  listener?.(msg);
}

export function setToastListener(fn: Listener | null): void {
  listener = fn;
}
