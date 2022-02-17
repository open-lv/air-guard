import sargsAPI from "../sargsAPI.js";

export default {
  name: "HomeComponent",
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
            <b>Statuss:</b> {{ wifiState.connected ? "Savienots" : "Nav savienots" }}
          </li>
          <li class="list-group-item">
            <b>SSID:</b> {{ wifiState.ssid ? wifiState.ssid : "Nav izvēlēts" }}
          </li>
          <li class="list-group-item">
            <b>Internets:</b> {{ wifiState.internet ? "Sasniedzams" : "Nav sasniedzams" }}
          </li>
        </ul>
      </div>
    </div>
    <div class="col-9" v-if="!loading">
      <div class="content bg-light">
        <div class="form-group">
          <label for="ssid">SSID:</label>
          <div class="input-group">
            <select v-model="selected" :disabled="loadingStations" id="ssid" class="form-control">
              <option v-for="station in stations" v-bind:value="station" :disabled="station.authmode === 'unknown'">
                {{ station.ssid }} ({{ station.bssid }}) {{ station.authmode !== 'open' ? '🔒' : 'Atvērts' }}
              </option>
            </select>
            <div class="input-group-append">
              <button @click="loadStations" :disabled="loadingStations" class="form-control btn btn-secondary">
                Atjaunot
              </button>
            </div>
          </div>
          <small class="form-text text-muted">Tava WiFi nosaukums</small>
        </div>
        <div class="form-group">
          <label for="ssid">Parole:</label>
          <input v-model="psk" id="psk" class="form-control" />
        </div>
        <div class="form-group">
          <button
            :disabled="!selected || loadingStations"
            class="btn btn-primary"
            @click="submitStation"
          >
            Saglabāt
          </button>
        </div>
      </div>
    </div>
  </div> `,
  data: () => {
    return {
      loading: true,
      selected: null,
      stations: null,
      psk: "",
    };
  },
  created() {
    this.getDataFromApi();
  },
  methods: {
    async getDataFromApi() {
      try {
        this.loading = true;
        this.stations = null;
        this.wifiState = (await sargsAPI.fetchState()).wifi;
        this.loading = false;
      } catch (e) {
        alert(`Notikusi neparedzēta kļūda: ${e}`);
      }

      this.loadStations();
    },
    async loadStations() {
      try {
        this.loadingStations = true;
        this.stations = null;
        this.stations = await sargsAPI.fetchStations();
        this.loadingStations = false;
      } catch (e) {
        alert(`Notikusi neparedzēta kļūda: ${e}`);
      }
    },
    async submitStation() {
      if (this.retrier) {
        clearTimeout(this.retrier);
      }
      await sargsAPI.submitStation(
        this.selected.bssid,
        this.selected.authmode !== "open" ? this.psk : null
      );
      this.retrier = setTimeout(this._retryFn, 1000, 10);
    },
    async _retryFn(retriesLeft) {
      this.wifiState = (await sargsAPI.fetchState()).wifi;
      if (!this.wifiState.connected && retriesLeft !== 0) {
        --retriesLeft;
        console.log("Wifi yet not connected, retrying...", {
          retriesLeft,
          wifiState: this.wifiState,
        });
        this.retrier = setTimeout(this._retryFn, 1000, retriesLeft);
        return;
      }

      if (!this.wifiState.connected && retriesLeft === 0) {
        console.log("Wifi yet not connected, retries exceeded...");
        return;
      }

      console.log("Wifi connected successfully!");
    },
  },
};
