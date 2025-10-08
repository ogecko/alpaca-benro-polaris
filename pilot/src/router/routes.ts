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
  {
    path: '/markdown',
    component: () => import('layouts/AltLayout.vue'),
    children: [{ path: '', component: () => import('pages/MarkdownPage.vue') }],
  },
  {
    path: '/test',
    component: () => import('layouts/AltLayout.vue'),
    children: [{ path: '', component: () => import('pages/TestPage.vue') }],
  },
  {
    path: '/kalman',
    component: () => import('layouts/AltLayout.vue'),
    children: [{ path: '', component: () => import('pages/AnalyseKalman.vue') }],
  },
  {
    path: '/pwm',
    component: () => import('layouts/AltLayout.vue'),
    children: [{ path: '', component: () => import('pages/AnalysePWM.vue') }],
  },
  {
    path: '/speed',
    component: () => import('layouts/AltLayout.vue'),
    children: [{ path: '', component: () => import('pages/AnalyseSpeed.vue') }],
  },
  {
    path: '/position',
    component: () => import('layouts/AltLayout.vue'),
    children: [{ path: '', component: () => import('pages/AnalysePosition.vue') }],
  },
  {
    path: '/sync',
    component: () => import('layouts/AltLayout.vue'),
    children: [{ path: '', component: () => import('pages/AnalyseSync.vue') }],
  },
  {
    path: '/about',
    component: () => import('layouts/AltLayout.vue'),
    children: [{ path: '', component: () => import('pages/AboutPage.vue') }],
  },
  {
    path: '/warning',
    component: () => import('layouts/AltLayout.vue'),
    children: [{ path: '', component: () => import('pages/WarningPage.vue') }],
  },


    // Always leave this as last one,
  // but you can also remove it
  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/ErrorNotFound.vue'),
  },
];

export default routes;
