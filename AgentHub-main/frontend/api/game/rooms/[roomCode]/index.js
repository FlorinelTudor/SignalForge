const handler = require("../../[...path].js");

module.exports = (req, res) => {
  req.query = { ...(req.query || {}), path: ["rooms", req.query.roomCode] };
  return handler(req, res);
};
