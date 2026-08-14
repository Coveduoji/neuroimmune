import { useEffect, useState } from 'react';
import { setToastListener } from '../toast';

export default function Toaster() {
  const [msgs, setMsgs] = useState<{ id: number; msg: string }[]>([]);

  useEffect(() => {
    setToastListener((msg) => {
      const id = Date.now() + Math.random();
      setMsgs((m) => [...m, { id, msg }]);
      setTimeout(() => setMsgs((m) => m.filter((x) => x.id !== id)), 3200);
    });
    return () => setToastListener(null);
  }, []);

  return (
    <div className="toasts">
      {msgs.map((m) => <div key={m.id} className="toast">{m.msg}</div>)}
    </div>
  );
}
