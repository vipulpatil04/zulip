export default function decompress(encodedString: string) {
  const decompressedArray = encodedString.split(/([A-Z])/g)
  const decompressedData = []
  let last = ''
  let i
  for (i = 1; i < decompressedArray.length; i += 2) {
    last =
      last.slice(0, decompressedArray[i].charCodeAt(0) - 65) +
      decompressedArray[i + 1]
    decompressedData.push(last)
  }

  return decompressedData
}
