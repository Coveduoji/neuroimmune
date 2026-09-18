import { http, downloadBlob, filenameFromDisposition } from './http';
import type { DashboardData, TrendData } from '../types/models';

export const dashboardApi = {
  dashboard: async () => (await http.get<DashboardData>('/dashboard')).data,
  trend: async (range = '24h') => (await http.get<TrendData>(`/trend?range=${range}`)).data,
  setKnob: async (knob: string) => (await http.put('/knob', { knob })).data,
  toleranceRemove: async (signature: string) => (await http.post('/tolerance/remove', { signature })).data,
  toleranceClear: async () => (await http.post('/tolerance/clear')).data,
  innateRemove: async (signature: string) => (await http.post('/innate/remove', { signature })).data,
  innateClear: async () => (await http.post('/innate/clear')).data,
  exportReport: async (body: object) => {
    const r = await http.post('/report/export', body, { responseType: 'blob' });
    downloadBlob(r.data as Blob, filenameFromDisposition(r.headers['content-disposition'] || '') || 'report');
  },
};
