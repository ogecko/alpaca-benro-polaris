<template>
  <q-page class="q-pa-sm dark-page">

    <StatusBanners />

    <!-- Header Row -->
    <div class="row q-pb-sm q-col-gutter-md items-center">
      <div class="col text-h6 q-ml-md">
        Sample Markdown Page
        <div class="text-caption text-grey-6">
        Provides a flexible way to add content to the application 
       </div>
      </div>
      <q-space />
    </div>
    <q-card flat bordered class="col">
      <div>
      <q-markdown class="q-pa-md" :no-mark="false">
# Heading 1
---
## Heading 2
---
### Heading 3

* Bullet 1
* Bullet 2
  + Bullet 2b

:::
This is a **test** of markdown 
:::

Inline `code` indented, with a ==marked== marked

    // Some comments
    line 1 of code
    line 2 of code
    line 3 of code


Syntax highlighting

```js
var foo = function (bar) {
  return bar++;
};

console.log(foo(5));
```

[External Link](https://github.com/quasarframework/quasar)

![Logo](icons/favicon-128x128.png)
        </q-markdown>

      </div>

    </q-card>
  </q-page>
</template>


<script setup lang="ts">
import StatusBanners from 'src/components/StatusBanners.vue'

</script>

<style lang="scss">
  .q-markdown--link {
    color: $grey-6;

    &:hover {
      text-decoration: underline;
      color: $grey-4;
    }
  }
</style>