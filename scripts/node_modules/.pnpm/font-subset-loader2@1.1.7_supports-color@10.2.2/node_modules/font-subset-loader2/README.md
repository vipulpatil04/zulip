# font subset loader for webpack 

> Thanks for dematerializer's work. Consider his package is obsolete, so I have forked this package and make it compatible with webpack 4+

Transforms a TTF font resource so that it contains only a specified subset of glyphs with all other glyphs stripped out.

## Install

`npm install font-subset-loader2 --save-dev`

## Usage

[Webpack Documentation: Using loaders](http://webpack.github.io/docs/using-loaders.html)

Glyphs like `!` or `,` conflict with webpack's query string syntax (i.e. `'font-subset-loader2?glyphs=hey,you!'`). It is therefore recommended to instead use a query object for passing the glyphs to the loader as a property:

``` javascript
{
    test: /\.ttf$/,
    use: [{
        loader: 'font-subset-loader2',
        options: { 
            glyphs: 'hey,you!' 
        }
    }]
}
// returns the file content of the subsetted file.ttf
// that contains only the specified glyphs 'h', 'e', 'y', ',', 'o', 'u' and '!'
```

## Usage with other loaders

Process subsetted `.ttf` files with file-loader:

``` javascript
rules: [
	{
        test: /\.ttf$/,
        use: [
            {
		        loader: 'file-loader'
            },
            {
                loader: 'font-subset-loader2',
                options: { 
                    glyphs: 'hey,you!' 
                }
            }
        ]
	},
]
```

Process subsetted `.ttf` files with url-loader:

``` javascript
rules: [
	{
        test: /\.ttf$/,
        use: [
            {
		        loader: 'url-loader'
            },
            {
                loader: 'font-subset-loader2',
                options: { 
                    glyphs: 'hey,you!' 
                }
            }
        ]
	},
]
```

## License

MIT
