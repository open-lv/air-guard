import sargsAPI from "../sargsAPI.js";

export default {
  template: `<div class="row">
    <div v-if="loading" class="col-12">
      <div class="content bg-light text-center">
        Notiek ielāde...
      </div>
    </div>
    <div class="col-3" v-if="!loading">
      <div class="side-panel bg-light">
        <ul class="list-group list-group-flush">
          <li class="list-group-item">
            <div class="row co2-measurement">
              <div class="col-2 measurement-label-col">
                <b class="measurement-label">CO2:</b>
              </div>
              <div class="col-10 measurement-value-col">
               <span class="measurement-value">
                 <b>{{ state.co2.ppm }}</b>ppm
               </span>
              </div>
            </div>
          </li>
          <li class="list-group-item p-0">
            <div class="input-group">
              <div class="form-control border-0">
                <b>WiFi:</b> {{ state.wifi.connected ? "Savienots" : "Nav savienots" }}
              </div>
              <div v-if="!state.wifi.connected" class="input-group-append">
                <router-link
                  to="/wifi-settings"
                  tag="button"
                  class="btn btn-primary rounded-0"
                  >Savienot</router-link
                >
              </div>
            </div>
          </li>
        </ul>
      </div>
    </div>
    <div class="col-9" v-if="!loading">
      <div class="content bg-light">
        Saturs
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
