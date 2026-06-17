const handler = require("../[...path].js");

module.exports = (req, res) => {
  req.query = { ...(req.query || {}), path: ["rooms"] };
  return handler(req, res);
};
