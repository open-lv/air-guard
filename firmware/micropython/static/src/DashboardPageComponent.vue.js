import sargsAPI from "../sargsAPI.js";

export default {
  template: `<div class="row">
    <div class="col mt-5">
      <img class="mx-auto d-block h-25" src="airguard.svg" />
      <div v-if="loading">Notiek ielāde...</div>
      <div v-if="!loading">
        <div class="row">
          <div class="col-2">CO2</div>
          <div class="col">{{ state.co2.ppm }} ({{ state.co2.status }})</div>
        </div>
        <div class="row">
          <div class="col-2">WiFi</div>
          <div class="col">
            {{ state.wifi.connected ? "Savienots" : "Nav savienots" }}
            <router-link
              to="/wifi-settings"
              tag="button"
              class="btn btn-primary"
              >Savienot</router-link
            >
          </div>
        </div>
      </div>
    </div>
  </div> `,
  data: () => {
    return {
      loading: true,
      state: null,
    };
  },
  created() {
    this.getDataFromApi();
  },
  methods: {
    async getDataFromApi() {
      this.state = await sargsAPI.fetchState();
      this.loading = false;
    },
  },
};
