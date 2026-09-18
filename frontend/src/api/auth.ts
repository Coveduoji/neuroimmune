import { http } from './http';
import type { AuthUser } from '../types/models';

export const authApi = {
  login: async (username: string, password: string) => {
    const { data } = await http.post<{ token: string; user: AuthUser }>('/auth/login', {
      username,
      password,
    });
    return data;
  },
  me: async () => (await http.get<AuthUser>('/auth/me')).data,
  changePassword: async (old_password: string, new_password: string) =>
    (await http.post<{ ok: boolean }>('/auth/change-password', { old_password, new_password })).data,
  register: async (body: object) => (await http.post<AuthUser>('/auth/register', body)).data,
  listUsers: async () => (await http.get<{ items: AuthUser[] }>('/auth/users')).data,
  updateUserRole: async (id: number, role: string) =>
    (await http.put<AuthUser>(`/auth/users/${id}`, { role })).data,
  resetUserPassword: async (id: number, new_password: string) =>
    (await http.post<{ ok: boolean }>(`/auth/users/${id}/reset-password`, { new_password })).data,
  deleteUser: async (id: number) => (await http.delete<{ ok: boolean }>(`/auth/users/${id}`)).data,
  permissions: async () => (await http.get<{ items: Record<string, string> }>('/auth/permissions')).data,
  updateUserPermissions: async (id: number, permissions: string[]) =>
    (await http.put<AuthUser>(`/auth/users/${id}/permissions`, { permissions })).data,
};
