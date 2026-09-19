var loaderUtils = require('loader-utils');
var Fontmin = require('fontmin');
module.exports = function(content) {
	this.cacheable && this.cacheable();
	var callback = this.async();
	var options = loaderUtils.getOptions(this);
	new Fontmin()
		.src(content)
		.use(Fontmin.glyph({ text: options.glyphs }))
		.run(function(err, files) {
			if (err) {
				console.log(err);
			} else {
				callback(err, files[0].contents);
			}
		});
};
module.exports.raw = true;
