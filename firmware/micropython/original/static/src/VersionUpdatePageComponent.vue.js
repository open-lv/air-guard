import sargsAPI from "../sargsAPI.js";

export default {
  template: `<div class="row">
    <div v-if="loading" class="col-12">
      <div class="content bg-light text-center">
        Notiek ielāde...
      </div>
    </div>
    <div class="col-12" v-if="!loading">
      <div class="content bg-light">
        <div v-for="(version, index) in versions" class="version" v-bind:class="{'old-version': index != 0}">
          <h2>
            {{formatVersion(version.tag_name)}}
            <small>{{formatDate(version.published_at)}}</small>
            <button
              class="btn btn-primary"
              v-if="index == 0"
              v-bind:disabled="updating"
              @click="updateVersion(getVersionNumber(version.tag_name))"
             >
               Atjaunot versiju
             </button>
          </h2>
          <pre v-if="version.body">{{version.body}}</pre>
          <hr v-if="index != versions.length - 1" />
        </div>
      </div>
    </div>
  </div>`,
  data: () => {
    return {
      loading: true,
      versions: null,
      updating: false,
    };
  },
  created() {
    this.getDataFromApi();
  },
  methods: {
    formatDate(dateString) {
      let timestamp = Date.parse(dateString);
      let datetime = new Date(timestamp);
      let padValue = (value) => {
        let string = String(value);
        return string.padStart(2, '0');
      };
      return datetime.getFullYear() + '-' + padValue(datetime.getMonth() + 1) + '-' + padValue(datetime.getDate());
    },
    formatVersion(versionString) {
      return 'Gaisa Sargs ' + this.getVersionNumber(versionString);
    },
    getVersionNumber(versionString) {
      return versionString.replace(/^\w+-/, '');
    },
    async getDataFromApi() {
      try {
        this.loading = true;
        this.versions = await sargsAPI.fetchVersions();
        this.loading = false;
      } catch (e) {
        alert(`Notikusi neparedzēta kļūda: ${e}`);
      }
    },
    async updateVersion(versionNumber) {
      if (!confirm("Atjainot versiju, Gaisa Sargs restartēsies.\nVai turpināt?")) {
        return;
      }
      this.updating = true;
      await sargsAPI.updateVersion(versionNumber);
    },
  },
};
