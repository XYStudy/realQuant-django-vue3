import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import ProfitDetail from '../views/ProfitDetail.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/profit/detail',
    name: 'ProfitDetail',
    component: ProfitDetail
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router