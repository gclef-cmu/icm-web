# 9. Filters

So far, this book has mostly studied _synthesis_: techniques like additive and modulation synthesis that create sound from scratch. But computer music is as much about _sculpting_ existing sound as it is about creating new sound. In this chapter we study {vocab}`filters`, the tools we use to process a signal we already have, whether it came from a synthesizer, a microphone, or another filter.

This chapter was heavily inspired by the treatment of [convolution in _Digital Signals Theory_ {cite}`mcfee2023digital`](https://brianmcfee.net/dstbook-site/content/ch03-convolution/Convolution.html), and we borrow much of its notation. Filter analysis and design is an extraordinarily deep subject, and we will only take a cursory look here. Readers who want to go further should consult [Julius Smith's _Introduction to Digital Filters_ {cite}`smith2007introduction`](https://ccrma.stanford.edu/~jos/filters), a thorough and audio-focused treatment.
