import { Line } from '@ant-design/plots';
import { Empty } from 'antd';
import dayjs from 'dayjs';
import type { TrendBucket } from '../types/models';

const fmt = (t: number) => dayjs(t * 1000).format('MM-DD HH:mm');

export default function TrendChart({ buckets }: { buckets: TrendBucket[] }) {
  if (!buckets || buckets.length === 0) return <Empty description="暂无流量数据" />;

  const data = buckets.flatMap((b) => [
    { time: fmt(b.t), value: b.total, series: '收到（全部）' },
    { time: fmt(b.t), value: b.surfaced, series: '上板' },
  ]);

  const config = {
    data,
    xField: 'time',
    yField: 'value',
    colorField: 'series',
    height: 260,
    scale: {
      color: { range: ['#2a78d6', '#1baf7a'] },
    },
    axis: {
      y: { title: false },
    },
    legend: { color: { position: 'top' } },
  };

  return <Line {...config} />;
}
