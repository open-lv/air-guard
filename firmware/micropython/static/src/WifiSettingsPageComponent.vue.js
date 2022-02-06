import sargsAPI from "../sargsAPI.js";

export default {
  name: "HomeComponent",
  template: `<div class="row">
    <select v-model="selected">
      <option v-for="station in stations" v-bind:value="station">
        {{ station.ssid }} ({{ station.bssid }}) {{ station.authmode !== 'open'
        ? '🔒' : 'Atvērts' }}
      </option>
    </select>
    <input v-model="psk" />
    <button
      :disabled="!selected"
      class="btn btn-primary"
      @click="submitStation"
    >
      Izvēlēties
    </button>
    <button class="btn btn-secondary" @click="reload">
      Izvēlēties
    </button>
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
        this.stations = await sargsAPI.fetchStations();
        this.wifiState = (await sargsAPI.fetchState()).wifi;
        this.loading = false;
      } catch (e) {
        alert(`Notikusi neparedzēta kļūda: ${e}`);
      }
    },
    async reload() {
      this.getDataFromApi();
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
