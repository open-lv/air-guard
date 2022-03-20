import Vue from "./vue.esm-browser.min.js";
import VueRouter from "./vue-router.esm.browser.min.js";
import DashboardPageComponent from "./src/DashboardPageComponent.vue.js";
import WifiSettingsPageComponent from "./src/WifiSettingsPageComponent.vue.js";
import VersionUpdatePageComponent from "./src/VersionUpdatePageComponent.vue.js";
import sargsAPI from "./sargsAPI.js";

Vue.use(VueRouter);

const router = new VueRouter({
  base: "/",
  routes: [
    { path: "/", component: DashboardPageComponent },
    { path: "/wifi-settings", component: WifiSettingsPageComponent },
    { path: "/version-update", component: VersionUpdatePageComponent },
  ],
});

const app = new Vue({
  router,
  template: `
    <div class="container" id="app">
      <div class="navbar navbar-light bg-light navbar-expand-sm px-3">
        <img class="navbar-brand" src="airguard.svg" />
        <ul class="navbar-nav mr-auto">
          <li class="nav-item" v-bind:class="{ active: $route.path === '/' }">
            <router-link to="/" class="nav-link">Galvenā</router-link>
          </li>
          <li class="nav-item" v-bind:class="{ active: $route.path === '/wifi-settings' }">
            <router-link to="/wifi-settings" class="nav-link">WiFi iestatījumi</router-link>
          </li>
          <li class="nav-item" v-bind:class="{ active: $route.path === '/version-update' }">
            <router-link to="/version-update" class="nav-link">
                Atjauninājumi
                <span class="badge bg-info" v-if="versionInfo && versionInfo.currentVersion != versionInfo.latestVersion">Jauna versija</span>
            </router-link>
          </li>
        </ul>
      </div>
      <router-view class="view"></router-view>
    </div>
  `,
  data: () => {
    return {
      versionInfo: null,
    };
  },
  created() {
    this.getDataFromApi();
  },
  methods: {
    async getDataFromApi() {
      this.versionInfo = (await sargsAPI.fetchState()).sargs;
    },
  },
}).$mount("#app");
