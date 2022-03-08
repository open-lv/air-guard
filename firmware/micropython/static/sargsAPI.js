const mock = true;

const loadData = (url) => {
  if (mock) {
    url = "mock/" + url + ".json";
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
    body: JSON.stringify(data),
  });
};

export default {
  fetchState: () => {
    return loadData("api/state");
  },
  fetchStations: () => {
    return loadData("api/stations");
  },
  submitStation: (ssid, password) => {
    submitData("api/stations/select", { ssid, password });
  },
};
