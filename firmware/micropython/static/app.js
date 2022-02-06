import Vue from "./vue.esm-browser.min.js";
import VueRouter from "./vue-router.esm.browser.min.js";
import DashboardPageComponent from "./src/DashboardPageComponent.vue.js";
import WifiSettingsPageComponent from "./src/WifiSettingsPageComponent.vue.js";

Vue.use(VueRouter);

const router = new VueRouter({
  base: "/",
  routes: [
    { path: "/", component: DashboardPageComponent },
    { path: "/wifi-settings", component: WifiSettingsPageComponent },
  ],
});

const app = new Vue({
  router,
  template: `
    <div class="container" id="app">
      <ul>
        <li v-if="$route.path !== '/'">
          <router-link to="/">Galvenā</router-link>
        </li>
      </ul>
      <router-view class="view"></router-view>
    </div>
  `,
}).$mount("#app");
