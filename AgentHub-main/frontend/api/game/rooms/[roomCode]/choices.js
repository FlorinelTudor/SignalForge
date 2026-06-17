const handler = require("../../[...path].js");

module.exports = (req, res) => {
  req.query = { ...(req.query || {}), path: ["rooms", req.query.roomCode, "choices"] };
  return handler(req, res);
};
