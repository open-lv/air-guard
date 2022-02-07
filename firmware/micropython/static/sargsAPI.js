const mock = true;

const loadData = (url) => {
  if (mock) {
    url = "mock/" + url;
  }

  return fetch(url).then((res) => res.json());
};

const submitData = (url, data) => {
  if (mock) {
    return new Promise((resolve) => {
      window.console.log(`Submitting to ${url}`, data);
      resolve();
    });
  }

  return fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });
};

export default {
  fetchState: () => {
    return loadData("api/state.json");
  },
  fetchStations: () => {
    return loadData("api/stations.json");
  },
  submitStation: (bssid, psk) => {
    submitData("select-station", { bssid, psk });
  },
};
