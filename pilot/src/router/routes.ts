import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('layouts/AltLayout.vue'),
    children: [{ path: '', component: () => import('pages/StartupPage.vue') }],
  },
  {
    path: '/connect',
    component: () => import('layouts/AltLayout.vue'),
    children: [{ path: '', component: () => import('pages/ConnectPage.vue') }],
  },
  {
    path: '/config',
    component: () => import('layouts/AltLayout.vue'),
    children: [{ path: '', component: () => import('pages/ConfigPage.vue') }],
  },
  {
    path: '/log',
    component: () => import('layouts/AltLayout.vue'),
    children: [{ path: '', component: () => import('pages/LogPage.vue') }],
  },
  // Always leave this as last one,
  // but you can also remove it
  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/ErrorNotFound.vue'),
  },
];

export default routes;
