import type { Report } from '../types';

export default function ReportView({ report }: { report: Report | null }) {
  if (!report) return <div className="empty">暂无结构化调查报告。</div>;
  const evidence = report.evidence ?? [];
  const attackChain = report.attack_chain ?? [];
  const iocs = report.iocs ?? [];
  const unknowns = report.unknowns ?? [];
  const remediations = report.remediations ?? [];

  return (
    <div className="report">
      <div>
        <span className="verdict">{report.verdict}</span>
        <span className="muted"> · 置信度 {report.confidence}</span>
      </div>
      {report.digest && <p className="digest">{report.digest}</p>}

      {evidence.length > 0 && (
        <>
          <h4>证据</h4>
          <ul>
            {evidence.map((e, i) => (
              <li key={i}>
                <b>{e.fact}</b> → {e.conclusion}
              </li>
            ))}
          </ul>
        </>
      )}

      {attackChain.length > 0 && (
        <>
          <h4>攻击链</h4>
          <ul>
            {attackChain.map((a, i) => (
              <li key={i}>
                <b>{a.phase}</b>：{a.description}
              </li>
            ))}
          </ul>
        </>
      )}

      {iocs.length > 0 && (
        <>
          <h4>IOC</h4>
          <div className="chips">
            {iocs.map((ioc, i) => (
              <span key={i} className="chip" title={ioc.context}>{ioc.value}</span>
            ))}
          </div>
        </>
      )}

      {unknowns.length > 0 && (
        <>
          <h4>待查</h4>
          <ul>{unknowns.map((u, i) => <li key={i}>{u}</li>)}</ul>
        </>
      )}

      {remediations.length > 0 && (
        <>
          <h4>处置建议</h4>
          <ul>{remediations.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </>
      )}
    </div>
  );
}
